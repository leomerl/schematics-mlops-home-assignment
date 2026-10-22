import hashlib
import mlflow
import pandas
from mlflow.data.pandas_dataset import from_pandas

DATASET_NAME = "bl_full_data"
DIGEST_LENGTH = 16
CHUNK_SIZE = 1024 * 1024

def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()

def log_dataset(data_path):
    df = pandas.read_csv(data_path, low_memory=False)
    dataset = from_pandas(
        df, source=data_path, name=DATASET_NAME, digest=file_sha256(data_path)[:DIGEST_LENGTH]
    )
    mlflow.log_input(dataset)
    mlflow.log_params({
        "data_rows": len(df),
        "data_start": df["session_dt"].min(),
        "data_end": df["session_dt"].max(),
    })