from typing import Any

import pandas as pd
from mlflow.pyfunc.model import PythonModelContext, PythonModel


class BLRankerModel(PythonModel):
    def load_context(self, context: PythonModelContext) -> None:
        self.artifact_paths = context.artifacts

    def predict(self, context: PythonModelContext, model_input: pd.DataFrame, params: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError("TBA")