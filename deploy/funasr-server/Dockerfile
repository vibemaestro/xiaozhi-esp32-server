FROM python:3.10-slim

WORKDIR /workspace

# 1. Cài đặt system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg libsndfile1 git gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# 2. Clone FunASR Source Code (Alibaba DAMO Academy)
RUN git clone https://github.com/alibaba-damo-academy/FunASR.git

# 3. Cài đặt các thư viện nặng trước (Tách layer để cache tốt hơn)
WORKDIR /workspace/FunASR
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -U pip && \
    # Cài đặt torch/torchaudio bản CPU để nhẹ và ổn định cho Swarm
    pip install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    # Cài đặt các thư viện bổ trợ
    pip install --no-cache-dir \
    transformers sentencepiece fastapi uvicorn[standard] python-multipart \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 4. Cài đặt FunASR từ source (Editable mode)
RUN pip install --no-cache-dir -e .

# 5. Copy server wrapper
COPY ./scripts/funasr_wss_server.py /workspace/FunASR/server.py

EXPOSE 10095

ENV PYTHONUNBUFFERED=1

# Clone repo Kiến trúc (để lấy file model.py cho Nano-2512)
RUN git clone https://github.com/FunAudioLLM/Fun-ASR.git /workspace/FunAudioLLM

# Đảm bảo PYTHONPATH trỏ vào cả runtime và kiến trúc
ENV PYTHONPATH=/workspace/FunASR:/workspace/FunAudioLLM

CMD python server.py \
     --asr_model /workspace/model_files \
     --asr_model_remote_code /workspace/FunAudioLLM/model.py \
     --device cpu \
     --certfile "" \
     --vad_model "" \
     --punc_model ""