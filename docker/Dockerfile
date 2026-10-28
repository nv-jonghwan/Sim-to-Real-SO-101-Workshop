FROM nvidia/cuda:13.0.0-base-ubuntu24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev python3-pip \
    git git-lfs curl ca-certificates build-essential cmake \
    libglvnd0 libgl1 libglx0 libopengl0 libegl1 libgles2 libvulkan1 \
    libx11-6 libxext6 libsm6 libglib2.0-0 \
    libxcursor1 libxrandr2 libxi6 libxinerama1 \
    libxkbcommon0 libxkbcommon-x11-0 \
    usbutils libusb-1.0-0 \
    ffmpeg \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages uv

ARG ISAACLAB_REF=5d208f81d4f8895b4e564ebebce232031171a3e8
ARG LEROBOT_REF=v0.6.0

ENV ISAACLAB_VENV=/workspace/IsaacLab/env_isaaclab
ENV VIRTUAL_ENV=${ISAACLAB_VENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV UV_NO_CACHE=1

WORKDIR /workspace

RUN git clone https://github.com/isaac-sim/IsaacLab.git \
    && git -C IsaacLab checkout "${ISAACLAB_REF}" \
    && uv venv --python /usr/bin/python3.12 "${ISAACLAB_VENV}"

WORKDIR /workspace/IsaacLab
RUN . "${ISAACLAB_VENV}/bin/activate" \
    && ./isaaclab.sh -i 'newton,ov[ovrtx],visualizer[newton]'

WORKDIR /workspace
RUN git clone https://github.com/huggingface/lerobot.git \
    && git -C lerobot checkout "${LEROBOT_REF}"

WORKDIR /workspace/lerobot
RUN . "${ISAACLAB_VENV}/bin/activate" \
    && uv pip install -e ".[training,groot,async,viz]"

COPY ./docker/lerobot-policy-patch/policy_server.py \
    /workspace/lerobot/src/lerobot/async_inference/policy_server.py

WORKDIR /workspace/Sim-to-Real-SO-101-Workshop
COPY . /workspace/Sim-to-Real-SO-101-Workshop

RUN . "${ISAACLAB_VENV}/bin/activate" \
    && uv pip install -e source/sim_to_real_so101

RUN rm -rf \
    /workspace/IsaacLab/.git \
    /workspace/IsaacLab/.github \
    /workspace/IsaacLab/docs \
    /workspace/IsaacLab/source/*/test \
    /workspace/lerobot/.git \
    /workspace/lerobot/.github \
    /workspace/lerobot/docs \
    /workspace/lerobot/tests

FROM nvidia/cuda:13.0.0-base-ubuntu24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv libpython3.12t64 libatomic1 \
    ca-certificates \
    libglvnd0 libgl1 libglx0 libopengl0 libegl1 libgles2 libvulkan1 \
    libx11-6 libxext6 libsm6 libglib2.0-0 \
    libxcursor1 libxrandr2 libxi6 libxinerama1 \
    libxkbcommon0 libxkbcommon-x11-0 \
    usbutils libusb-1.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV ISAACLAB_VENV=/workspace/IsaacLab/env_isaaclab
ENV VIRTUAL_ENV=${ISAACLAB_VENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV UV_NO_CACHE=1

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /workspace /workspace

WORKDIR /workspace/Sim-to-Real-SO-101-Workshop

ENV NVIDIA_VISIBLE_DEVICES=all
ENV CUDA_DEVICE_ORDER=PCI_BUS_ID
ENV NVIDIA_DRIVER_CAPABILITIES=all
ENV OVRTX_SHADER_CACHE_PATH=/root/.cache/ovrtx

RUN mkdir -p /tmp/pycache \
    && chmod 1777 /tmp/pycache \
    && cat docker/utils.sh >> /root/.bashrc \
    && chmod +x docker/entrypoint.sh
ENV PYTHONPYCACHEPREFIX=/tmp/pycache

ENTRYPOINT ["/workspace/Sim-to-Real-SO-101-Workshop/docker/entrypoint.sh"]
CMD ["bash"]
