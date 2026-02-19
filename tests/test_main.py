"""Test suite for the Agentic RAG application."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch

from src.config import ConfigManager, BusinessCalculation, ClientConfig, DataSource
from src.visualization import DataVisualizer


class TestConfigManager:
    """Test configuration management."""
    
    def test_calculation_evaluation(self):
        """Test business calculation evaluation."""
        manager = ConfigManager()
        manager.config = ClientConfig(
            client_name="Test",
            data_source=DataSource(type="bigquery"),
            business_calculations=[
                BusinessCalculation(
                    name="test_calc",
                    description="Test calculation",
                    formula="a + b",
                    parameters=["a", "b"]
                )
            ]
        )
        
        result = manager.evaluate_calculation("test_calc", {"a": 10, "b": 20})
        assert result == 30
    
    def test_calculation_not_found(self):
        """Test error handling for missing calculation."""
        manager = ConfigManager()
        manager.config = ClientConfig(
            client_name="Test",
            data_source=DataSource(type="bigquery"),
            business_calculations=[]
        )
        
        with pytest.raises(ValueError):
            manager.evaluate_calculation("nonexistent", {})


class TestDataVisualizer:
    """Test data visualization."""
    
    def test_bar_chart_creation(self):
        """Test bar chart creation."""
        visualizer = DataVisualizer()
        df = pd.DataFrame({
            'category': ['A', 'B', 'C'],
            'value': [10, 20, 30]
        })
        
        fig = visualizer.auto_visualize(df, chart_type='bar')
        assert fig is not None
        assert len(fig.data) > 0
    
    def test_line_chart_creation(self):
        """Test line chart creation."""
        visualizer = DataVisualizer()
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'value': [10, 20, 15, 25, 30]
        })
        
        fig = visualizer.auto_visualize(df, chart_type='line')
        assert fig is not None
        assert len(fig.data) > 0
    
    def test_empty_dataframe(self):
        """Test handling of empty dataframe."""
        visualizer = DataVisualizer()
        df = pd.DataFrame()
        
        fig = visualizer.auto_visualize(df)
        assert fig is not None


class TestBigQueryConnector:
    """Test BigQuery connector (mocked)."""
    
    @patch('src.connectors.bigquery.bigquery.Client')
    def test_validate_query(self, mock_client):
        """Test query validation."""
        from src.connectors import BigQueryConnector
        
        # Mock successful validation
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024
        mock_client.return_value.query.return_value = mock_job
        
        connector = BigQueryConnector()
        result = connector.validate_query("SELECT 1")
        
        assert result["valid"] == True


def test_imports():
    """Test that all modules can be imported."""
    from src.agents import AgenticRAG
    from src.config import ConfigManager
    from src.connectors import BigQueryConnector
    from src.llm import LLMFactory
    from src.visualization import DataVisualizer
    
    assert AgenticRAG is not None
    assert ConfigManager is not None
    assert BigQueryConnector is not None
    assert LLMFactory is not None
    assert DataVisualizer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
