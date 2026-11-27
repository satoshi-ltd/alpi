import os

# alpi registers its curated native models itself (alpi/providers/native_models.yaml), so litellm need not download its price map on every start.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

__version__ = "0.19.47"
