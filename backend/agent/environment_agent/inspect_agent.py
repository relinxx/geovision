import sys
import inspect
import pandas as pd

from agent.environment_agent.agent import SuitabilityAgent

print("Before creating agent, xgboost loaded in this Python process?:", "xgboost" in sys.modules)

agent = SuitabilityAgent()

print("After creating agent, xgboost loaded?:", "xgboost" in sys.modules)
print("Risk data loaded?:", not agent.risk_data.empty)
print("Risk data rows:", len(agent.risk_data))
print("Risk data columns:", list(agent.risk_data.columns))

df = pd.DataFrame({"parcel_id": ["3340300400"]})
result = agent.predict(df)

print("After prediction, xgboost loaded?:", "xgboost" in sys.modules)
print(result)

print("\nDoes SuitabilityAgent.predict source mention xgboost/XGBRegressor/load_model?")
src = inspect.getsource(SuitabilityAgent.predict)
for word in ["xgboost", "XGBRegressor", "load_model", "Booster"]:
    print(word, "=>", word in src)
