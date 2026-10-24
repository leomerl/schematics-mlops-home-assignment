import os


class Registry:
    REGISTERED_MODEL_NAME = os.environ.get("REGISTERED_MODEL_NAME", "bl_ranker")
    CHAMPION_ALIAS = "champion"
    CHALLENGER_ALIAS = "challenger"
