"""Data visualization components."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, Dict, Any, List, Tuple

MONTH_NAMES = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
               7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}


class DataVisualizer:
    """Creates visualizations from data."""
    
    def __init__(self, theme: str = "plotly"):
        """Initialize visualizer with theme."""
        self.theme = theme

    # ------------------------------------------------------------------
    # Smart column selection helpers
    # ------------------------------------------------------------------

    def _pick_xy(self, df: pd.DataFrame) -> Tuple[str, List[str]]:
        """
        Pick the best x-axis column and the metric y-axis columns.

        Rules (in order):
        1. Prefer explicit dimension columns: month, date, year (when not all same value),
           quarter, week, period, day, name, category, label, type, brand, county, store.
        2. Among numeric columns, the x candidate is the one with the fewest unique values
           relative to row count (i.e. a grouping dimension like month 1-12).
        3. y columns are the remaining numeric columns with the largest value range,
           excluding columns that look like IDs or time dimensions.
        """
        col_names_lower = [c.lower() for c in df.columns]
        numeric_cols = list(df.select_dtypes(include=['number']).columns)
        text_cols = [c for c in df.columns if c not in numeric_cols]

        # Dimension keywords that should be x-axis
        dim_keywords = ['month', 'date', 'week', 'quarter', 'day', 'period',
                        'name', 'category', 'label', 'type', 'brand', 'county',
                        'store', 'city', 'region', 'vendor', 'description', 'item']

        # --- Choose x col ---
        x_col = None

        # First prefer text/categorical columns (always good x-axis)
        if text_cols:
            x_col = text_cols[0]

        # Then look for a dimension keyword among all columns
        if x_col is None:
            for kw in dim_keywords:
                for col in df.columns:
                    if kw in col.lower():
                        x_col = col
                        break
                if x_col:
                    break

        # Then pick the numeric column with fewest unique values (e.g. month=1-12)
        if x_col is None and numeric_cols:
            x_col = min(numeric_cols, key=lambda c: df[c].nunique())

        if x_col is None:
            x_col = df.columns[0]

        # --- Choose y cols (metrics) ---
        # Exclude x_col and any column that looks like a pure dimension (year, month, id)
        exclude_for_y = {x_col.lower()}
        dim_only = {'year', 'month', 'week', 'quarter', 'day', 'id'}
        y_candidates = [
            c for c in numeric_cols
            if c.lower() not in exclude_for_y and c.lower() not in dim_only
        ]

        # If nothing left after exclusion, fall back to all numeric except x
        if not y_candidates:
            y_candidates = [c for c in numeric_cols if c != x_col]

        # Sort by value range descending so the main metric comes first
        if y_candidates:
            y_candidates.sort(key=lambda c: df[c].max() - df[c].min(), reverse=True)

        # Fall back: if still empty, use first column that isn't x
        if not y_candidates:
            y_candidates = [c for c in df.columns if c != x_col][:1]

        return x_col, y_candidates

    def _format_x_axis(self, df: pd.DataFrame, x_col: str) -> pd.DataFrame:
        """Convert numeric month/quarter columns to readable labels."""
        df = df.copy()
        col_lower = x_col.lower()
        if 'month' in col_lower and df[x_col].dtype in ['int64', 'float64', 'int32']:
            if df[x_col].between(1, 12).all():
                df[x_col] = df[x_col].map(MONTH_NAMES)
        return df

    # ------------------------------------------------------------------

    def auto_visualize(self, df: pd.DataFrame, chart_type: Optional[str] = None) -> go.Figure:
        """Automatically create appropriate visualization based on data."""
        if df.empty:
            return self._create_empty_chart("No data to visualize")
        
        # Auto-detect chart type if not specified
        if not chart_type:
            chart_type = self._detect_chart_type(df)
        
        visualizers = {
            'bar': self._create_bar_chart,
            'line': self._create_line_chart,
            'scatter': self._create_scatter_plot,
            'pie': self._create_pie_chart,
            'histogram': self._create_histogram,
            'box': self._create_box_plot,
            'heatmap': self._create_heatmap,
            'table': self._create_table
        }
        
        visualizer = visualizers.get(chart_type.lower(), self._create_bar_chart)
        return visualizer(df)
    
    def _detect_chart_type(self, df: pd.DataFrame) -> str:
        """Auto-detect appropriate chart type based on data."""
        num_cols = len(df.columns)
        num_rows = len(df)
        numeric_cols = df.select_dtypes(include=['number']).columns
        col_names = ' '.join(df.columns).lower()

        # Single metric row → table display is cleaner, but we use bar if possible
        if num_rows == 1:
            return 'bar'

        # Single column
        if num_cols == 1:
            if df[df.columns[0]].dtype in ['object', 'category']:
                return 'bar'
            # Only use histogram for truly continuous data with many rows
            return 'histogram' if num_rows > 20 else 'bar'

        # Time-series columns → line chart
        time_keywords = ['month', 'year', 'date', 'week', 'quarter', 'time', 'period', 'day']
        if any(kw in col_names for kw in time_keywords):
            return 'line' if num_rows > 3 else 'bar'

        # Two columns
        if num_cols == 2:
            if len(numeric_cols) == 2 and num_rows > 10:
                return 'scatter'
            return 'bar'

        # Multiple columns with time series
        if 'date' in col_names or 'time' in col_names:
            return 'line'

        # Default to bar chart
        return 'bar'
    
    def _create_bar_chart(self, df: pd.DataFrame) -> go.Figure:
        """Create a bar chart."""
        if len(df.columns) < 2:
            value_counts = df[df.columns[0]].value_counts()
            fig = px.bar(
                x=value_counts.index,
                y=value_counts.values,
                labels={'x': df.columns[0], 'y': 'Count'},
                template=self.theme
            )
        else:
            x_col, y_cols = self._pick_xy(df)
            df = self._format_x_axis(df, x_col)
            y_col = y_cols[0] if y_cols else df.columns[-1]
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                template=self.theme,
                color_discrete_sequence=['#636EFA']
            )
        fig.update_layout(
            xaxis_title=None,
            yaxis_title=None,
            bargap=0.3,
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig
    
    def _create_line_chart(self, df: pd.DataFrame) -> go.Figure:
        """Create a line chart with smart x/y selection."""
        x_col, y_cols = self._pick_xy(df)
        df = self._format_x_axis(df, x_col)

        if not y_cols:
            return self._create_empty_chart("No numeric data for line chart")

        fig = go.Figure()
        colors = ['#00CC96', '#636EFA', '#EF553B', '#AB63FA', '#FFA15A']
        for i, col in enumerate(y_cols[:5]):
            fig.add_trace(go.Scatter(
                x=df[x_col],
                y=df[col],
                mode='lines+markers',
                name=col,
                line=dict(width=2.5, color=colors[i % len(colors)]),
                marker=dict(size=7)
            ))

        fig.update_layout(
            template=self.theme,
            xaxis_title=x_col,
            yaxis_title=y_cols[0] if len(y_cols) == 1 else None,
            hovermode='x unified',
            plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        # Format y-axis for large numbers
        max_val = max(df[col].max() for col in y_cols if col in df)
        if max_val > 1_000_000:
            fig.update_yaxes(tickformat='$.3s')
        elif max_val > 1_000:
            fig.update_yaxes(tickformat=',')
        return fig
    
    def _create_scatter_plot(self, df: pd.DataFrame) -> go.Figure:
        """Create a scatter plot."""
        numeric_cols = df.select_dtypes(include=['number']).columns
        
        if len(numeric_cols) < 2:
            return self._create_empty_chart("Need at least 2 numeric columns for scatter plot")
        
        fig = px.scatter(
            df,
            x=numeric_cols[0],
            y=numeric_cols[1],
            template=self.theme
        )
        
        fig.update_layout(title="Scatter Plot")
        return fig
    
    def _create_pie_chart(self, df: pd.DataFrame) -> go.Figure:
        """Create a pie chart."""
        if len(df.columns) < 2:
            value_counts = df[df.columns[0]].value_counts()
            # Limit to top 10 for readability
            if len(value_counts) > 10:
                value_counts = value_counts.head(10)
            fig = px.pie(
                values=value_counts.values,
                names=value_counts.index,
                template=self.theme,
                hole=0.3  # Donut style for better readability
            )
        else:
            # Limit to top 10 categories for readability
            df_plot = df.copy()
            if len(df_plot) > 10:
                df_plot = df_plot.nlargest(10, df.columns[1])
            
            fig = px.pie(
                df_plot,
                values=df.columns[1],
                names=df.columns[0],
                template=self.theme,
                hole=0.3  # Donut style for better readability
            )
        
        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Value: %{value:,.0f}<br>Percentage: %{percent}<extra></extra>'
        )
        fig.update_layout(
            title="Pie Chart",
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.05
            )
        )
        return fig
    
    def _create_histogram(self, df: pd.DataFrame) -> go.Figure:
        """Create a histogram."""
        numeric_cols = df.select_dtypes(include=['number']).columns
        
        if len(numeric_cols) == 0:
            return self._create_empty_chart("No numeric data for histogram")
        
        fig = px.histogram(
            df,
            x=numeric_cols[0],
            template=self.theme
        )
        
        fig.update_layout(title="Histogram")
        return fig
    
    def _create_box_plot(self, df: pd.DataFrame) -> go.Figure:
        """Create a box plot."""
        numeric_cols = df.select_dtypes(include=['number']).columns
        
        if len(numeric_cols) == 0:
            return self._create_empty_chart("No numeric data for box plot")
        
        fig = go.Figure()
        
        for col in numeric_cols:
            fig.add_trace(go.Box(y=df[col], name=col))
        
        fig.update_layout(
            title="Box Plot",
            template=self.theme
        )
        return fig
    
    def _create_heatmap(self, df: pd.DataFrame) -> go.Figure:
        """Create a heatmap (correlation matrix)."""
        numeric_df = df.select_dtypes(include=['number'])
        
        if numeric_df.empty:
            return self._create_empty_chart("No numeric data for heatmap")
        
        corr_matrix = numeric_df.corr()
        
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.columns,
            colorscale='RdBu',
            zmid=0
        ))
        
        fig.update_layout(
            title="Correlation Heatmap",
            template=self.theme
        )
        return fig
    
    def _create_table(self, df: pd.DataFrame) -> go.Figure:
        """Create an interactive table."""
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=list(df.columns),
                fill_color='paleturquoise',
                align='left'
            ),
            cells=dict(
                values=[df[col] for col in df.columns],
                fill_color='lavender',
                align='left'
            )
        )])
        
        fig.update_layout(title="Data Table")
        return fig
    
    def _create_empty_chart(self, message: str) -> go.Figure:
        """Create an empty chart with a message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20)
        )
        fig.update_layout(template=self.theme)
        return fig
    
    def create_multi_chart(self, df: pd.DataFrame, chart_configs: List[Dict[str, Any]]) -> List[go.Figure]:
        """Create multiple charts from configurations."""
        figures = []
        
        for config in chart_configs:
            chart_type = config.get('type', 'bar')
            columns = config.get('columns')
            
            if columns:
                chart_df = df[columns]
            else:
                chart_df = df
            
            fig = self.auto_visualize(chart_df, chart_type)
            
            if 'title' in config:
                fig.update_layout(title=config['title'])
            
            figures.append(fig)
        
        return figures
