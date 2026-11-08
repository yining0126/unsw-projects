# COMP9414 Assignment 1: Artificial Neural Networks

**Course:** COMP9414 Artificial Intelligence, UNSW, 24T2  
**Author:** Yining Liu  
**Assignment:** Air Quality Classification and NOx Regression

## Table of Contents

- [Overview](#overview)
- [Dataset and Preprocessing](#dataset-and-preprocessing)
- [Classification Task](#classification-task)
- [Regression Task](#regression-task)
- [Results](#results)
- [Running the Notebook](#running-the-notebook)
- [Included Project Files](#included-project-files)

## Overview

This assignment applies artificial neural networks to the Air Quality dataset. It contains two prediction tasks:

1. **Binary classification:** predict whether the measured carbon monoxide concentration, `CO(GT)`, is above the dataset mean.
2. **Regression:** estimate the nitrogen oxides concentration, `NOx(GT)`, from other air quality measurements.

The work was completed individually as a Jupyter notebook. It covers exploratory analysis, missing-value handling, feature selection, model training, evaluation, and prediction on additional input data.

## Dataset and Preprocessing

The project folder includes the course-provided hourly air quality dataset, `AirQualityUCI_Students.xlsx`, and the additional input file, `newvalues_9414.csv`. Missing values in the dataset are encoded as `-200`.

The notebook:

- inspects variable ranges and distributions with summary statistics and plots;
- replaces `-200` values with missing values and applies linear interpolation;
- examines relationships between variables using a correlation matrix;
- standardizes model input features with `StandardScaler`.

## Classification Task

The target is defined as 1 when `CO(GT)` is greater than its mean in the preprocessed dataset, and 0 otherwise. The notebook uses a fully connected neural network with two hidden layers (32 and 16 ReLU units), dropout, and a sigmoid output. It is trained with binary cross-entropy and the Adam optimizer.

The data is split into training, validation, and test sets using a 70/15/15 random split (`random_state=42`). The model reports loss and accuracy curves, a confusion matrix, accuracy, and precision.

## Regression Task

The regression model estimates `NOx(GT)` using a fully connected network with two hidden layers (32 and 16 ReLU units), dropout, and L2 regularization. It uses a linear output layer, mean squared error loss, and the Adam optimizer.

The notebook preserves the row order and uses a 70/20/10 train/validation/test split. It plots training and validation loss, compares estimated and actual validation values, and reports RMSE and MAE on the test set.

## Results

Results recorded in the notebook:

| Task | Evaluation set | Samples | Result |
|---|---|---:|---|
| CO classification | Test | 1,254 | Accuracy: 0.90; Precision: 0.90 |
| NOx regression | Test | 837 | RMSE: 78.41; MAE: 57.50 |

The classification test confusion matrix was:

|  | Actual negative | Actual positive |
|---|---:|---:|
| Predicted negative | 669 | 67 |
| Predicted positive | 54 | 464 |


## Running the Notebook

1. Install the packages listed in [`requirements.txt`](requirements.txt).
2. Keep the notebook, `AirQualityUCI_Students.xlsx`, and `newvalues_9414.csv` in the working directory.
3. In the notebook, set `file_name` to `AirQualityUCI_Students.xlsx`. The current notebook filename string contains extra spaces (`AirQualityUCI _ Students.xlsx`), so it will not match the uploaded Excel filename until updated.
4. Run the notebook cells in order.

The final notebook section loads `newvalues_9414.csv` for additional predictions and evaluation.

## Included Project Files

The project folder contains:

- `9414ass1_YiningLiu.ipynb` — assignment notebook;
- `AirQualityUCI_Students.xlsx` — course-provided dataset;
- `newvalues_9414.csv` — additional input data for prediction and evaluation;
- `classification_model.h5` and `regression_model.h5` — trained neural network models;
- `Cscaler.pkl` and `Rscaler.pkl` — fitted feature scalers;
- `requirements.txt` — Python package dependencies.

Running the training cells recreates the model and scaler files in the working directory.
