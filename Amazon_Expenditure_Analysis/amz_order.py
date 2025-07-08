import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, dash_table

df = pd.read_csv('/Users/priyankam/Documents/Amazon/amazon_order_jun_2024_may_2025.csv')
df['Total Owed'] = df['Total Owed'].astype(str).str.replace(r'[\u20B9,]', '', regex=True).str.strip()
df['Total Owed'] = pd.to_numeric(df['Total Owed'], errors='coerce')
df = df.dropna(subset=['Total Owed'])

df['Class_Label'] = df['Class_Label'].str.upper()
label_map = {'H': 'Home', 'A': 'Accessories', 'D': 'Dress', 'K': 'Kitchen', 'G': 'Groceries'}
df['Category'] = df['Class_Label'].map(label_map)
df['Clean Date'] = df['Order Date'].str.extract(r'(^\d{4}-\d{2}-\d{2})')

total_owed = df['Total Owed'].sum()
top_date = df['Clean Date'].mode()[0]
top_date_count = df['Clean Date'].value_counts()[top_date]

category_totals = df.groupby('Category')['Total Owed'].sum().reset_index().sort_values(by='Total Owed', ascending=False)
category_totals['Total Owed Display'] = category_totals['Total Owed'].apply(lambda x: f"₹{x:,.2f}")

fig_pie = px.pie(category_totals, names='Category', values='Total Owed', title='Total Owed by Category', hole=0.4)
fig_pie.update_layout(paper_bgcolor='black', font_color='white')


df['Month'] = pd.to_datetime(df['Clean Date']).dt.to_period('M').astype(str)
month_totals = df.groupby('Month')['Total Owed'].sum().reset_index()
fig_bar = px.bar(month_totals, x='Month', y='Total Owed', title='Monthly Spending (Total Owed)', color_discrete_sequence=['#1f77b4'])
fig_bar.update_layout(paper_bgcolor='black', font_color='white', plot_bgcolor='black')
fig_bar.update_xaxes(tickangle=45)

top_items_per_class = {}
for label, group in df.groupby('Category'):
    top_10 = (group.groupby('Product Name')
              .agg({'Total Owed': 'sum', 'Clean Date': 'max'})
              .reset_index()
              .sort_values(by='Total Owed', ascending=False)
              .head(10))
    top_10['Total Owed'] = top_10['Total Owed'].apply(lambda x: f"₹{x:,.2f}")
    top_10 = top_10.rename(columns={'Clean Date': 'Last Order Date'})
    top_items_per_class[label] = top_10

app = Dash(__name__)
app.title = "Amazon Dashboard"

app.layout = html.Div(style={'backgroundColor': 'black', 'color': 'white', 'padding': '20px'}, children=[
    html.H1("Amazon Order Dashboard", style={'textAlign': 'center'}),

    html.Div([  
        html.Div([
            html.H4("Total Owed", style={'textAlign': 'center'}),
            html.H2(f"₹{total_owed:,.2f}", style={'textAlign': 'center'})
        ], style={'backgroundColor': '#222', 'padding': '20px', 'margin': '10px', 'borderRadius': '10px', 'width': '45%'}),

        html.Div([
            html.H4("Top Purchase Date", style={'textAlign': 'center'}),
            html.H2(f"{top_date} ({top_date_count} orders)", style={'textAlign': 'center'})
        ], style={'backgroundColor': '#222', 'padding': '20px', 'margin': '10px', 'borderRadius': '10px', 'width': '45%'}),
    ], style={'display': 'flex', 'justifyContent': 'center'}),

    html.Div([  
        html.Div([dcc.Graph(figure=fig_pie)], style={'width': '48%', 'display': 'inline-block'}),
        html.Div([dcc.Graph(figure=fig_bar)], style={'width': '48%', 'display': 'inline-block'}),
    ], style={'marginTop': '20px'}),

    html.H2("Total Owed per Category", style={'textAlign': 'center', 'marginTop': '40px'}),
    html.Div([
        html.Div([
            html.H4(row['Category'], style={'textAlign': 'center'}),
            html.H3(row['Total Owed Display'], style={'textAlign': 'center'})
        ], style={
            'flex': '1', 'margin': '10px', 'padding': '20px',
            'border': '1px solid white', 'borderRadius': '10px', 'backgroundColor': '#111'
        })
        for _, row in category_totals.iterrows()
    ], style={'display': 'flex', 'justifyContent': 'space-between', 'flexWrap': 'wrap'}),

    html.H2("Top 10 Items per Category", style={'textAlign': 'center', 'marginTop': '40px'}),
    html.Div([
        html.Div([
            html.H4(category, style={'textAlign': 'center'}),
            dash_table.DataTable(
                data=top_df.to_dict('records'),
                columns=[{'name': i, 'id': i} for i in top_df.columns],
                style_table={'overflowX': 'auto'},
                style_cell={
                    'padding': '5px', 'textAlign': 'left',
                    'minWidth': '120px', 'maxWidth': '120px',
                    'overflow': 'hidden', 'textOverflow': 'ellipsis',
                    'color': 'white', 'backgroundColor': '#222'
                },
                style_header={'backgroundColor': '#444', 'fontWeight': 'bold', 'color': 'white'},
                tooltip_data=[
                    { 'Product Name': {'value': row['Product Name'], 'type': 'text'} }
                    for row in top_df.to_dict('records')
                ],
                tooltip_duration=None,
                css=[
                    {
                        'selector': '.dash-table-tooltip',
                        'rule': 'background-color: #f5f5f5; color: black; font-size: 14px;'
                    }
                ]
            )
        ], style={
            'flex': '0 0 45%', 'margin': '10px', 'padding': '10px', 'border': '1px solid white',
            'borderRadius': '10px', 'backgroundColor': '#111'
        }) for category, top_df in top_items_per_class.items()
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center'})
])

if __name__ == '__main__':
    app.run(debug=True, port=8051)
