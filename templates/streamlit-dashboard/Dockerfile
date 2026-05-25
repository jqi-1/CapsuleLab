FROM python:3.11-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    streamlit \
    jupyterlab \
    pandas \
    numpy \
    matplotlib \
    plotly

COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt

EXPOSE 8501

CMD ["bash"]
