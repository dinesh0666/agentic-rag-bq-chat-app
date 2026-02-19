"""Configuration management for dynamic client setups."""

import os
import yaml
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class BusinessCalculation(BaseModel):
    """Business calculation configuration."""
    name: str
    description: str
    formula: str
    parameters: List[str] = Field(default_factory=list)
    output_format: Optional[str] = None


class DataSource(BaseModel):
    """Data source configuration."""
    type: str  # bigquery, postgres, etc.
    project_id: Optional[str] = None
    dataset_id: Optional[str] = None
    connection_string: Optional[str] = None
    tables: List[str] = Field(default_factory=list)


class VisualizationConfig(BaseModel):
    """Visualization preferences."""
    default_chart_type: str = "bar"
    color_scheme: str = "plotly"
    enable_interactive: bool = True


class ClientConfig(BaseModel):
    """Complete client configuration."""
    client_name: str
    data_source: DataSource
    business_calculations: List[BusinessCalculation] = Field(default_factory=list)
    visualization: VisualizationConfig = Field(default_factory=VisualizationConfig)
    custom_instructions: Optional[str] = None
    domain_context: Optional[str] = None


class ConfigManager:
    """Manages client configurations."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager."""
        self.config_path = config_path or os.getenv("CONFIG_PATH", "./configs/client_config.yaml")
        self.config: Optional[ClientConfig] = None
        
        if os.path.exists(self.config_path):
            self.load_config()
    
    def load_config(self, config_path: Optional[str] = None) -> ClientConfig:
        """Load configuration from YAML file."""
        path = config_path or self.config_path
        
        with open(path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        self.config = ClientConfig(**config_data)
        return self.config
    
    def save_config(self, config: ClientConfig, config_path: Optional[str] = None):
        """Save configuration to YAML file."""
        path = config_path or self.config_path
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w') as f:
            yaml.dump(config.model_dump(), f, default_flow_style=False)
    
    def get_calculation(self, name: str) -> Optional[BusinessCalculation]:
        """Get a specific business calculation by name."""
        if not self.config:
            return None
        
        for calc in self.config.business_calculations:
            if calc.name.lower() == name.lower():
                return calc
        return None
    
    def get_all_calculations(self) -> List[BusinessCalculation]:
        """Get all business calculations."""
        if not self.config:
            return []
        return self.config.business_calculations
    
    def get_calculation_context(self) -> str:
        """Get formatted business calculation context for LLM."""
        if not self.config or not self.config.business_calculations:
            return "No business calculations configured."
        
        context_parts = ["Available Business Calculations:"]
        
        for calc in self.config.business_calculations:
            calc_info = f"\n- {calc.name}: {calc.description}"
            if calc.formula:
                calc_info += f"\n  Formula: {calc.formula}"
            if calc.parameters:
                calc_info += f"\n  Parameters: {', '.join(calc.parameters)}"
            context_parts.append(calc_info)
        
        return "\n".join(context_parts)
    
    def evaluate_calculation(self, name: str, parameters: Dict[str, Any]) -> Any:
        """Evaluate a business calculation with given parameters."""
        calc = self.get_calculation(name)
        if not calc:
            raise ValueError(f"Calculation '{name}' not found")
        
        # Create a safe evaluation environment
        safe_dict = {
            '__builtins__': {},
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'round': round,
            **parameters
        }
        
        try:
            result = eval(calc.formula, safe_dict)
            return result
        except Exception as e:
            raise ValueError(f"Error evaluating calculation '{name}': {str(e)}")
    
    def get_domain_context(self) -> str:
        """Get domain-specific context for the client."""
        if not self.config:
            return ""
        
        context_parts = []
        
        if self.config.client_name:
            context_parts.append(f"Client: {self.config.client_name}")
        
        if self.config.domain_context:
            context_parts.append(f"Domain Context: {self.config.domain_context}")
        
        if self.config.custom_instructions:
            context_parts.append(f"Custom Instructions: {self.config.custom_instructions}")
        
        return "\n".join(context_parts)
