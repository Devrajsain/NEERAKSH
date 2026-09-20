import json
import math
from pydantic import BaseModel, field_serializer, model_validator
from fastapi.encoders import jsonable_encoder

class TestModel(BaseModel):
    log_likelihood: float | None

    @field_serializer('log_likelihood')
    def serialize_log_likelihood(self, log_likelihood: float | None, _info):
        if log_likelihood is not None and math.isinf(log_likelihood):
            return None
        if log_likelihood is not None and math.isnan(log_likelihood):
            return None
        return log_likelihood

def run_test():
    model = TestModel(log_likelihood=float('-inf'))
    print("Pydantic representation:", model)
    
    encoded = jsonable_encoder(model)
    print("jsonable_encoder output:", encoded)
    
    try:
        json.dumps(encoded, allow_nan=False)
        print("Success: json.dumps strict mode passed!")
    except Exception as e:
        print("Failed:", str(e))

if __name__ == "__main__":
    run_test()
