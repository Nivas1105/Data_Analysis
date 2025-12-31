# Telecom Customer Churn Analysis

A comprehensive exploratory data analysis (EDA) project analyzing customer churn patterns in the telecommunications industry.

## Overview

This project performs detailed analysis on the Telco Customer Churn dataset to identify key factors influencing customer retention and churn. The analysis uses statistical methods, visualizations, and data exploration techniques to uncover actionable insights.

## Dataset

**Source**: WA_Fn-UseC_-Telco-Customer-Churn.csv

The dataset contains customer information including:
- **Demographics**: Gender, Senior Citizen status, Partner, Dependents
- **Services**: Phone Service, Multiple Lines, Internet Service, Online Security, Online Backup, Device Protection, Tech Support, Streaming TV, Streaming Movies
- **Account Information**: Tenure, Contract type, Payment Method, Paperless Billing, Monthly Charges, Total Charges
- **Target Variable**: Churn (Yes/No)

## Analysis Components

### 1. Data Cleaning
- Handling missing values
- Data type conversions
- Outlier detection and treatment

### 2. Exploratory Data Analysis
- **Univariate Analysis**: Distribution of individual features
- **Bivariate Analysis**: Relationships between features and churn
- **Correlation Analysis**: Identifying key predictors of churn

### 3. Key Visualizations
- Churn rate distribution
- Customer demographics analysis
- Service subscription patterns
- Contract type impact on churn
- Monthly and total charges distribution
- Tenure analysis

### 4. Business Insights
- Identification of high-risk customer segments
- Service features correlated with retention
- Contract and payment method impacts
- Recommendations for reducing churn

## Technologies Used

- **Python 3.x**
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computations
- **Matplotlib**: Static visualizations
- **Seaborn**: Statistical data visualization

## Installation

```bash
pip install pandas numpy matplotlib seaborn jupyter
```

## Usage

1. Ensure the dataset `WA_Fn-UseC_-Telco-Customer-Churn.csv` is in the project directory
2. Open the notebook:
   ```bash
   jupyter notebook churn_analysis.ipynb
   ```
3. Run all cells to execute the complete analysis

## Key Findings

The analysis reveals:
- Customer tenure is strongly correlated with churn probability
- Month-to-month contracts have higher churn rates compared to long-term contracts
- Customers with electronic payment methods show different churn patterns
- Specific service combinations are associated with higher retention rates
- Senior citizens and customers without partners/dependents may have different churn behaviors

## Project Structure

```
Churn_Analysis/
├── WA_Fn-UseC_-Telco-Customer-Churn.csv  # Dataset
├── churn_analysis.ipynb                   # Main analysis notebook
└── README.md                              # This file
```

## Applications

This analysis can help:
- **Customer Retention Teams**: Identify at-risk customers
- **Marketing Teams**: Design targeted retention campaigns
- **Product Teams**: Optimize service bundles
- **Business Strategy**: Inform pricing and contract strategies

## Future Work

- Implement predictive machine learning models for churn prediction
- Perform customer segmentation using clustering techniques
- Build a real-time churn prediction dashboard
- Conduct A/B testing simulations for retention strategies
