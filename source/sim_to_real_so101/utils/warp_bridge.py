# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Stream ordering at Isaac Lab's Torch manager interfaces."""

from contextlib import nullcontext

import torch
import warp as wp


def manager_stream(device):
    """Order Warp launches with both Newton and the calling Torch stream."""
    device = wp.get_device(str(device))
    if device.is_cpu:
        return nullcontext()
    return wp.ScopedStream(
        wp.stream_from_torch(torch.cuda.current_stream(device.ordinal)),
        sync_enter=True,
        sync_exit=True,
    )
