# AEM AI Content Agent

## Prerequisites

### 1. AEM SDK

Download from [Adobe Software Distribution](https://experience.adobe.com/#/downloads) (Adobe account required).

For local AEM instance setup and startup instructions, see [docs/AEM_SETUP.md](docs/AEM_SETUP.md).


### 3. Alibaba Cloud Account

- Sign up at [Alibaba Cloud](https://www.alibabacloud.com/)
- Enable Model Studio (MaaS)
- Generate API key and add to `.env`

### 4. Python 3.11+

```bash
pip install -r requirements.txt
```

## Running the backend and frontend apps

1. Start the backend API:

```bash
uvicorn api.main:app --reload
```

2. Start the Streamlit review UI in a separate terminal:

```bash
streamlit run ui/app.py
```

3. Open the UI in your browser at:

```
http://localhost:8501
```
