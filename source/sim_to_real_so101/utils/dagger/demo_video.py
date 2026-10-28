# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DAgger session video with a banner showing whether the policy or the operator controls the arm."""

import queue
import threading

import av
import cv2
import numpy as np

_BANNER_HEIGHT = 40
_GREEN, _RED, _GREY = (46, 160, 67), (207, 34, 46), (110, 110, 110)
_LABELS = {
    "autonomous": ("POLICY", _GREEN),
    "guide_starting": ("HUMAN TAKEOVER", _RED),
    "correcting": ("HUMAN TAKEOVER", _RED),
}


class DemoVideo:
    """Write camera views side by side under a control banner to an H.264 MP4.

    A background thread encodes the frames. ``add`` drops a frame while the
    encoder is more than two seconds behind, so the control loop never waits.
    Encoding errors are printed and stop only the video. Phases other than
    policy and human control show their name in grey.
    """

    def __init__(self, path, fps):
        self._limit = 2 * fps
        self._frames = queue.Queue()
        self._thread = threading.Thread(target=self._encode, args=(path, fps), name="demo-video", daemon=True)
        self._thread.start()

    def add(self, images, phase):
        """Queue uint8 HxWx3 camera images and the session phase as one frame."""
        if self._frames.qsize() < self._limit:
            self._frames.put((images, phase))

    def close(self):
        """Encode the queued frames and finish the file."""
        self._frames.put(None)
        self._thread.join()

    def _encode(self, path, fps):
        try:
            with av.open(str(path), "w") as container:
                stream = None
                while (item := self._frames.get()) is not None:
                    frame = labelled_frame(*item)
                    if stream is None:
                        stream = container.add_stream("libx264", rate=fps)
                        stream.height, stream.width = frame.shape[:2]
                        stream.pix_fmt = "yuv420p"
                    container.mux(stream.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")))
                if stream is not None:
                    container.mux(stream.encode())
        except Exception as exc:  # noqa: BLE001 - a demo video must never stop the session
            print(f"[DAGGER]: Demo video stopped: {exc}", flush=True)


def labelled_frame(images, phase):
    """Camera images side by side, scaled to the first one's height, under a control banner."""
    height = images[0].shape[0]
    views = np.hstack([
        image if image.shape[0] == height else cv2.resize(image, (round(image.shape[1] * height / image.shape[0]), height))
        for image in images
    ])
    text, color = _LABELS.get(phase, (phase.replace("_", " ").upper(), _GREY))
    banner = np.full((_BANNER_HEIGHT, views.shape[1], 3), color, dtype=np.uint8)
    cv2.putText(banner, text, (12, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
    frame = np.vstack([banner, views])
    return frame[: frame.shape[0] // 2 * 2, : frame.shape[1] // 2 * 2]  # H.264 4:2:0 needs even sides
