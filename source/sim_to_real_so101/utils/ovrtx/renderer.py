# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""OVRtx 0.5 renderer integration for workshop runtime scene writes."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import numpy as np
from isaaclab_ov.renderers.ovrtx_renderer import OVRTXRenderer
from isaaclab_ov.renderers.ovrtx_renderer_cfg import OVRTXRendererCfg
from pxr import Gf, Sdf

from .blur import CameraGaussianBlur
from .ovstage_writes import expand_prim_paths, write_asset_path, write_attribute

logger = logging.getLogger(__name__)

_AMBIENT_LIGHT_ATTR = "omni:rtx:rt:ambientLight:intensity"


class SO101OVRTXRenderer(OVRTXRenderer):
    """Use OVRtx multi-camera rendering and expose workshop OVStage writes."""

    def __init__(self, cfg: OVRTXRendererCfg):
        os.environ["ISAAC_LAB_OVRTX_USE_OVSTAGE"] = "1"
        super().__init__(cfg)
        self._pending_writes: list[tuple[str, str, Any, Any]] = []
        self._pending_camera_reads: set[int] = set()
        self._camera_responses = cfg.camera_responses
        self._camera_paths: dict[str, str] = {}
        self._camera_blur: dict[str, CameraGaussianBlur] = {}

    @staticmethod
    def _disable_ambient_fill(content: str) -> str:
        authored = f"float {_AMBIENT_LIGHT_ATTR} = 1.0"
        if authored not in content:
            raise RuntimeError("OVRtx render product has no authored ambient fill")
        return content.replace(authored, f"float {_AMBIENT_LIGHT_ATTR} = 0.0", 1)

    def _apply_camera_response(self, content: str, camera_path: str, product_path: str) -> str:
        """Author one camera's fixed response on its tiled render product."""
        attributes = next(
            (values for suffix, values in self._camera_responses.items() if camera_path.endswith(suffix)),
            None,
        )
        if attributes is None:
            return content
        layer = Sdf.Layer.CreateAnonymous("camera-response.usda")
        layer.ImportFromString(content)
        product = layer.GetPrimAtPath(product_path)
        for name, value in attributes.items():
            if isinstance(value, bool):
                value_type = Sdf.ValueTypeNames.Bool
            elif isinstance(value, str):
                value_type = Sdf.ValueTypeNames.Token
            elif isinstance(value, tuple):
                value_type = Sdf.ValueTypeNames.Color3f
                value = Gf.Vec3f(*value)
            else:
                value_type = Sdf.ValueTypeNames.Float
            Sdf.AttributeSpec(product, name, value_type).default = value
        return layer.ExportToString()

    def create_render_data(self, spec):
        from isaaclab_ov.renderers import ovrtx_renderer as ovrtx_module

        original = ovrtx_module.build_render_product_as_string

        def build_workshop_render_product(camera_spec, render_data, **kwargs):
            content = self._disable_ambient_fill(original(camera_spec, render_data, **kwargs))
            return self._apply_camera_response(
                content, camera_spec.camera_prim_paths[0],
                f"/{render_data.render_scope_name}/{render_data.render_product_name}",
            )

        ovrtx_module.build_render_product_as_string = (
            build_workshop_render_product
        )
        try:
            render_data = super().create_render_data(spec)
        finally:
            ovrtx_module.build_render_product_as_string = original
        self._camera_paths[render_data.render_product_path] = spec.camera_prim_paths[0]
        self._flush_pending_writes()
        return render_data

    def render_batch(self, render_data) -> None:
        """Batch sequential scalar camera reads into one native submission."""
        if (
            not self._use_ovstage
            or len(self._camera_render_data) < 2
            or len(render_data) != 1
        ):
            self._pending_camera_reads.clear()
            super().render_batch(render_data)
            return

        camera_index = self._camera_render_data.index(render_data[0])
        if (
            not self._pending_camera_reads
            or camera_index not in self._pending_camera_reads
        ):
            super().render_batch(tuple(self._camera_render_data))
            self._pending_camera_reads = set(range(len(self._camera_render_data)))
        self._pending_camera_reads.discard(camera_index)

    @property
    def _num_envs(self) -> int:
        return self._camera_render_data[0].num_envs

    def write_prim_attribute(
        self,
        prim_path: str,
        attribute_name: str,
        tensor: np.ndarray,
        semantic=None,
    ) -> bool:
        """Mirror a USD attribute edit into the renderer-owned scene."""
        return self._runtime_write(
            prim_path, attribute_name, np.asarray(tensor), semantic
        )

    def write_prim_asset_path(
        self,
        prim_path: str,
        attribute_name: str,
        asset_path: str,
    ) -> bool:
        """Mirror a USD asset-path edit into the renderer-owned scene."""
        return self._runtime_write(prim_path, attribute_name, asset_path, None)

    def _runtime_write(self, prim_path, attribute_name, value, semantic) -> bool:
        if not self._camera_render_data:
            self._pending_writes.append(
                (prim_path, attribute_name, value, semantic)
            )
            return True

        prim_paths = expand_prim_paths(prim_path, self._num_envs)
        try:
            if isinstance(value, str):
                write_asset_path(
                    self.backend.stage,
                    self.backend.paths,
                    prim_paths,
                    attribute_name,
                    value,
                    self._current_ordinal,
                )
            else:
                write_attribute(
                    self.backend.stage,
                    self.backend.paths,
                    prim_paths,
                    attribute_name,
                    value,
                    self._current_ordinal,
                    semantic,
                )
        except Exception as exc:  # noqa: BLE001 - the OVStage mirror is optional
            logger.warning(
                "OVStage write failed (%s on %s): %s", attribute_name, prim_paths, exc
            )
            return False
        return True

    def _flush_pending_writes(self) -> None:
        pending, self._pending_writes = self._pending_writes, []
        for prim_path, attribute_name, value, semantic in pending:
            self._runtime_write(prim_path, attribute_name, value, semantic)

    def set_camera_blur(self, camera_prim_path: str, env_ids, sigma_px) -> None:
        """Set episode blur for selected environments of a known workshop camera."""
        pattern = camera_prim_path.replace("{ENV_REGEX_NS}", "/World/envs/env_.*")
        for data in self._camera_render_data:
            product = data.render_product_path
            if re.fullmatch(pattern, self._camera_paths[product]):
                if product not in self._camera_blur:
                    self._camera_blur[product] = CameraGaussianBlur(data.num_envs, self._device)
                self._camera_blur[product].set_sigma(env_ids, sigma_px)
                return
        raise ValueError(f"Camera {camera_prim_path!r} has no registered render product.")

    def _process_render_products(self, render_data, products) -> None:
        super()._process_render_products(render_data, products)
        for data in render_data:
            blur = self._camera_blur.get(data.render_product_path)
            if blur is not None and "rgba" in data.warp_buffers:
                blur.apply(data.warp_buffers["rgba"])

    def close(self) -> None:
        self._camera_paths.clear()
        self._camera_blur.clear()
        self._pending_writes.clear()
        self._pending_camera_reads.clear()
        super().close()
