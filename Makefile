.PHONY: install data build analyze app all

install:
	pip install -r requirements.txt

data:
	python scripts/download_data.py

build:
	python src/pipeline.py

analyze:
	python src/analysis.py

app:
	streamlit run app/streamlit_app.py

all: data build analyze
