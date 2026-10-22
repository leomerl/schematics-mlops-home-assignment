class ProdArtifacts:
    CATBOOST = "CB_bl_lead.cbm"
    TFM_CONTEXT = "payout_tfm_context.joblib"
    CLIENTS = "all_clients.csv"
    ALL = (CATBOOST, TFM_CONTEXT, CLIENTS)


class ArtifactKeys:
    CATBOOST = "catboost"
    TFM_CONTEXT = "tfm_context"
    CLIENTS = "clients"
