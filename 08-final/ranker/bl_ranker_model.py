import os
import tempfile
import threading
import pandas as pd
from typing import Any
from mlflow.pyfunc.model import PythonModelContext, PythonModel
from ranker.prod_artifacts import ArtifactKeys
from researcher.bl_exp_payout_predictor import BLPayoutModelsPredict
import researcher.bl_exp_payout_predictor as predictor_module

NO_RESULT = {"expected_payout": 0, "prob_lead": 0}
SURVEY_COLUMNS = [
    "credit_score", "industry", "loan_amount", "loan_reason",
    "monthly_revenue", "time_in_business", "device_type", "business_type",
]
MIN_SURVEY_ANSWERS = 5

class BLRankerModel(PythonModel):
    def load_context(self, context: PythonModelContext) -> None:
        artifacts_dir = os.path.join(os.path.dirname(context.artifacts[ArtifactKeys.CATBOOST]), "")
        log_dir = os.environ.get("PREDICTOR_LOG_PATH", tempfile.gettempdir())

        self.predictor = BLPayoutModelsPredict(artifacts_dir, user_data=None, log_path=log_dir)
        self.model_tfm, self.tfm_columns, self.cb_model = self.predictor.load_models()
        self.lock = threading.Lock()

    def predict(self, context: PythonModelContext, model_input: pd.DataFrame, params: dict[str, Any] | None = None) -> Any:
        user_data = model_input.iloc[0].to_dict()
        answered = sum(pd.notna(user_data.get(column)) for column in SURVEY_COLUMNS)
        if answered < MIN_SURVEY_ANSWERS:
            return NO_RESULT
        with self.lock:
            predictor_module.user_data = user_data
            bl_data = self.predictor.bl_preprocessing()
            if bl_data.shape[0] == 0:
                return NO_RESULT
            return self.predictor.prediction_expected_payout(
                bl_data, self.model_tfm, self.tfm_columns, self.cb_model
            )