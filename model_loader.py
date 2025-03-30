from model_loader_core import ModelLoader
from model_types import ModelType

# Create a simple passthrough to access the loader in persona
class ModelLoaderWrapper:
    def __init__(self, persona_manager):
        self.persona_manager = persona_manager
        
    def load_model(self, model_type: ModelType):
        return self.persona_manager.load_model(model_type)
        
    def is_model_loaded(self, model_type: ModelType) -> bool:
        return model_type in self.persona_manager.models

# This will be initialized after persona_manager is created
model_loader = None

def initialize_model_loader(persona_manager_instance):
    global model_loader
    model_loader = ModelLoaderWrapper(persona_manager_instance) 