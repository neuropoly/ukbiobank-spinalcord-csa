#!/usr/bin/env python
# -*- coding: utf-8
# Computes statistical analysis for ukbiobank project
#
# For usage, type: uk_compute_stats -h

# Authors: Sandrine Bédard

import os
import argparse
import pandas as pd
import numpy as np
import logging
import sys
import yaml
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.formula.api import ols

from sklearn.feature_selection import RFECV
from sklearn.svm import SVR
#import seaborn as sns

#import pipeline_ukbiobank.cli.select_subjects as ss
from sklearn.linear_model import LinearRegression
from statsmodels.stats.multicomp import pairwise_tukeyhsd

FNAME_LOG = 'log_stats.txt'

# Initialize logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # default: logging.DEBUG, logging.INFO
hdlr = logging.StreamHandler(sys.stdout)
logging.root.addHandler(hdlr)

PREDICTORS = ['Sex', 'Height', 'Weight', 'Intracranial volume', 'Age'] # Add units of each

def get_parser():
    parser = argparse.ArgumentParser(
        description="Computes the statistical analysis for the ukbiobank project",#add list of metrics that will be computed
        prog=os.path.basename(__file__).strip('.py')
        )
    parser.add_argument('-path-results',
                        required=True,
                        metavar='<dir_path>',
                        help="Folder that includes the output csv file from get_subjects_info")
    parser.add_argument('-dataFile',
                        required=False,
                        default='data_ukbiobank.csv',
                        metavar='<file>',
                        help="Filename of the data, output file of uk_get_subject_info, default: data_ukbiobank.csv  ")
    parser.add_argument('-exclude',
                        metavar='<file>',
                        required=False,
                        help=".yml list of subjects to exclude from statistical analysis."
                        ) #add format of the list

    return parser

FILENAME = 'data_ukbiobank_test.csv'

#0. remove subjects --> OK
#1. Caractérisation des données
    #Nombre de sujet --> OK
    #Moyenne --> OK
    #mediane --> OK
    #Variance --> OK
    #COV --> OK
    #Int confiance (après je crois) --> OK
    # % H vs F --> OK
    # Plage de données pour taille, volume, poids, age --> OK
    #OUTPUT tableau + CSV (AJOUTER) ajouter unités
#2. Coff corrélation --> OK
    #OUTPUT tableau + CSV 
#3 Multivariate regression (stepwise)
    #normalise data before ???
    #full and stepwise model --> ok, ajouter AIC
    #output coeff.txt   --> ok for stepwise
#4 Test tuckey diff T1w et T2w
#5 Pertinence modèle
    # collinéarité (scatterplot avec age et height)
    # Résidus
    # R^2 --> ok, faire un texte
    # Analyse variance
    # Intervalle de prédiction
#6 Logfile --> OK, mais en ajouter partout
# TODO: gérer l'écriture des fichiers

def compute_statistics(df):
    """
    Compute statistics such as mean, std, COV, etc. per contrast type
    :param df Pandas structure
    """
    contrasts = ['T1w_CSA', 'T2w_CSA']
    metrics = ['number of sub','mean','std','med','95ci', 'COV', 'max', 'min']
    stats = {}

    for contrast in contrasts:
        stats[contrast] = {}
        for metric in metrics:
            stats[contrast][metric] = {}

    for contrast in contrasts:
        stats[contrast]['number of sub'] = len(df[contrast])
        stats[contrast]['mean'] = np.mean(df[contrast])
        stats[contrast]['std'] = np.std(df[contrast])
        stats[contrast]['med']= np.median(df[contrast])
        stats[contrast]['95ci'] = 1.96*np.std(df[contrast])/np.sqrt(len(df[contrast]))
        stats[contrast]['COV'] = np.std(df[contrast]) / np.mean(df[contrast])
        stats[contrast]['max'] = np.max(df[contrast])
        stats[contrast]['min'] = np.min(df[contrast])
    return stats

def compute_predictors_statistic(df):
    """
    Compute statistics such as mean, min, max for each predictor
    :param df Pandas structure
    """
    stats={}
    metrics = ['min', 'max', 'med', 'mean']
    for predictor in PREDICTORS:
        stats[predictor] = {}
        for metric in metrics:
            stats[predictor][metric] = {}
    for predictor in PREDICTORS:
        stats[predictor]['min'] = np.min(df[predictor])
        stats[predictor]['max'] = np.max(df[predictor])
        stats[predictor]['med'] = np.median(df[predictor])
        stats[predictor]['mean'] = np.mean(df[predictor])
    stats['Sex'] = {}
    stats['Sex']['%_M'] = 100*(np.count_nonzero(df['Sex']) / len(df['Sex']))
    stats['Sex']['%_F'] = 100 - stats['Sex']['%_M']
    # Writes 
    output_text_stats(stats)
    return stats
def output_text_stats(stats):
    """
    Embed statistical results into sentences so they can easily be copy/pasted into a manuscript.
    """
    logger.info('Sex statistic:')
    logger.info('{} % of male  and {} % of female.'.format(stats['Sex']['%_M'],
                                                                             stats['Sex']['%_F']))
    logger.info('Height statistic:')
    logger.info('   Height between {} and {} cm, median height {} cm, mean height {} cm.'.format(stats['Height']['min'],
                                                                            stats['Height']['max'],
                                                                            stats['Height']['med'],
                                                                            stats['Height']['mean']))
    logger.info('Weight statistic:')
    logger.info('   Weight between {} and {} kg, median weight {} kg, mean weight {} kg.'.format(stats['Weight']['min'],
                                                                            stats['Weight']['max'],
                                                                            stats['Weight']['med'],
                                                                            stats['Weight']['mean']))
    logger.info('Age statistic:')
    logger.info('   Age between {} and {} y.o., median age {} y.o., mean age {} y.o..'.format(stats['Age']['min'],
                                                                            stats['Age']['max'],
                                                                            stats['Age']['med'],
                                                                            stats['Age']['mean']))
    logger.info('Intracranial Volume statistic:')
    logger.info('   Intracranial volume between {} and {} mm^3, median intracranial volume {} mm^3, mean intracranial volume {} mm^3.'.format(stats['Intracranial volume']['min'],
                                                                            stats['Intracranial volume']['max'],
                                                                            stats['Intracranial volume']['med'],
                                                                            stats['Intracranial volume']['mean']))
def config_table(corr_table, filename): # add units to table
    plt.figure(linewidth=2,
           tight_layout={'pad':1},
           figsize=(15,4)
          )
    rcolors = plt.cm.BuPu(np.full(len(corr_table.index), 0.1))
    ccolors = plt.cm.BuPu(np.full(len(corr_table.columns), 0.1))
    table = plt.table(np.round(corr_table.values, 4), 
            rowLabels = corr_table.index,
            colLabels = corr_table.columns,
            rowLoc='center',
            loc = 'center',
            cellLoc = 'center',
            colColours = ccolors,
            rowColours = rcolors
            )

    table.scale(1, 1.5)
    # Hide axes
    ax = plt.gca()
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    # Hide axes border
    plt.box(on=None)
 
    plt.draw()
    fig = plt.gcf()
    plt.savefig(filename,
            edgecolor=fig.get_edgecolor(),
            facecolor=fig.get_facecolor(),
            )
    logger.info('Created: ' + filename)


def get_correlation_table(df) :
    corr_table = df.corr()
    return corr_table

def get_predictors_rank(x,y):

    estimator = SVR(kernel="linear")
    selector = RFECV(estimator, step=1, cv=5)
    selector = selector.fit(x, y_T1w)
    return selector.ranking_

def generate_linear_model(x, y, selected_features):
    x = x[selected_features]
    x = sm.add_constant(x)

    model = sm.OLS(y, x)
    results = model.fit()
    return results

#def get_scatterplot(x):
    #sns.pairplot(x)
def compute_stepwise(X,y, threshold_in, threshold_out): # TODO: add AIC cretaria
    """
    Performs backword and forward feature selection based on p-values 
    
    Args:
        X (panda.DataFrame): Candidate predictors
        y (panda.DataFrame): Candidate predictors with target
        threshold_in: include a feature if its p-value < threshold_in
        threshold_out: exclude a feature if its p-value > threshold_out

    Retruns:
        included: list of selected features
    
    """
    included = []
    while True:
        changed = False
        #Forward step
        excluded = list(set(X.columns)-set(included))
        new_pval = pd.Series(index=excluded, dtype = np.float64)
        #print('Excluded', excluded)
        for new_column in excluded:
            model = sm.OLS(y, sm.add_constant(pd.DataFrame(X[included+[new_column]]))).fit()
            new_pval[new_column] = model.pvalues[new_column]
        best_pval = new_pval.min()
        
        #print(best_pval)
        if best_pval < threshold_in:
            best_feature = excluded[new_pval.argmin()] # problème d'ordre ici --> OK!!
            included.append(best_feature)
            changed=True
            logger.info('Add  {:30} with p-value {:.6}'.format(best_feature, best_pval))

        # backward step
        model = sm.OLS(y, sm.add_constant(pd.DataFrame(X[included]))).fit()
        # use all coefs except intercept
        pvalues = model.pvalues.iloc[1:]
        worst_pval = pvalues.max() # null if pvalues is empty
        if worst_pval > threshold_out:
            changed=True
            worst_feature = pvalues.argmax()
            #print('worst', worst_feature)
            included.remove(worst_feature)
            if verbose:
                logger.info('Drop {:30} with p-value {:.6}'.format(worst_feature, worst_pval))
        if not changed:
            break
    return included

def compute_regression_CSA(x,y, p_in, p_out, contrast):
    
    logger.info("Stepwise linear regression {}:".format(contrast))
    selected_features = compute_stepwise(x, y, p_in, p_out)
    
    # Generates model for T1w et T2w with p-value stepwise linear regression
    model = generate_linear_model(x,y, selected_features)
    
    # TODO : faire un fonction qui formate tout et écrit tous les fichier
    with open('summary_stepwise'+ contrast + '.txt', 'w') as fh: # Modifier le lieu, faire un dossier
        fh.write(model.summary(title = 'Stepwise linear regression of ' + contrast).as_text())
    (model.params).to_csv('coeff_stepwise'+ contrast + '.csv', header = None)


    #Generates liner regression with all predictors
    model_full = generate_linear_model(x,y, PREDICTORS)

    with open('summary_full_'+ contrast + '.txt', 'w') as fh: # Modifier le lieu, faire un dossier
        fh.write(model_full.summary(title = 'Full linear regression of ' + contrast).as_text())
    (model.params).to_csv('coeff_stepwise'+ contrast + '.csv', header = None)
    #Compares full and reduced models
    compared_models = compare_models(model, model_full, 'Stepwise_model', 'Full model')


def compare_models(model_1, model_2,model_1_name, model_2_name  ):
    columns = ['Model', 'R^2', 'R^2_adj', 'F_p-value','F_value', 'AIC', 'df_res'] # pas sur si nécessaire
    table = pd.DataFrame(columns= columns)
    table['Model'] = [model_1_name, model_2_name]
    table['R^2'] = [model_1.rsquared, model_2.rsquared]
    table['R^2_adj'] = [model_1.rsquared_adj, model_2.rsquared_adj]
    table['F_p-value'] = [model_1.f_pvalue, model_2.f_pvalue]
    table['F_value'] = [model_1.fvalue, model_2.fvalue]
    table['AIC'] = [model_1.aic, model_2.aic]
    table['df_res'] = [model_1.df_resid, model_2.df_resid]
    
    return table

def remove_subjects(df, dict_exclude_subj):
    """
    Removes subjects from exclude list if given and all subjects that are missing any parameter.
    Writes in log list of removed subjects.
    Args:
        df (panda.DataFrame): Dataframe with all subjects.
    Returns
        df_updated (panda.DataFrame): Dataframe with subjects removed.
    """
    subjects_removed = df.loc[pd.isnull(df).any(1), :].index.values
    df = df.drop(index = dict_exclude_subj)
    df_updated = df.dropna(0,how = 'any').reset_index(drop=True)
    subjects_removed = np.append(subjects_removed,dict_exclude_subj)
    logger.info("Subjects removed: {}".format(subjects_removed))
    return df_updated

def main():
    parser = get_parser()
    args = parser.parse_args()

    # Creates a panda dataFrame from data file .csv 
    df = (pd.read_csv(args.path_results +'/' + args.dataFile)).set_index('Subject')
    
    #create dict with subjects to exclude if input yml config file is passed
    if args.exclude is not None:
        #check if input yml file exists
        if os.path.isfile(args.exclude):
            fname_yml = args.exclude
        else:
            sys.exit("ERROR: Input yml file {} does not exist or path is wrong.".format(args.exclude))
        with open(fname_yml, 'r') as stream:
            try:
                dict_exclude_subj = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.error(exc)
    else:
        # initialize empty dict if no config yml file is passed
        dict_exclude_subj = dict()

    # Dump log file there
    if os.path.exists(FNAME_LOG):
        os.remove(FNAME_LOG)
    fh = logging.FileHandler(os.path.join(os.path.abspath(os.curdir), FNAME_LOG))
    logging.root.addHandler(fh)
#_______________________________________________________________________________________________________ 
#0. Removes all subjects that are missing a parameter or CSA value and subjects from exclude list.
    df = remove_subjects(df, dict_exclude_subj) 

# Initialize path of results figues
    path_figures = args.path_results + '/figures'
    if not os.path.isdir(path_figures):
        os.mkdir(args.path_results + '/figures')
# _____________________________________________________________________________________________________
#1. Compute stats

    #1.1 Compute stats of T1w CSA and T2w CSA
    stats_csa = compute_statistics(df)
    stats_csa_df = pd.DataFrame.from_dict(stats_csa)
    # Format and save stats of csa as a table
    config_table(stats_csa_df, path_figures + '/stats_CSA.png' ) # add units to table

    #add save as csv file

    #1.2. Compute stats of the predictors
    stats_predictors = compute_predictors_statistic(df)
    stats_predictors_df = pd.DataFrame.from_dict(stats_predictors)

    # Format and save stats of csa as a table
    config_table(stats_predictors_df, path_figures + '/stats_param.png' )
    #add save as csv file and .png figure
#_______________________________________________________________________________________________________ 
#2. Correlation matrix
    corr_table = get_correlation_table(df)
    logger.info("Correlation matrix: {}".format(corr_table))
    # Saves an .png of the correlation matrix in the results folder
    config_table(corr_table, path_figures+ '/corr_table.png')
#________________________________________________________________________________________________________    
#3 Stepwise linear regression | Faire un fonction avec tout ça
    x = df.drop(columns = ['T1w_CSA', 'T2w_CSA'])
    y_T1w = df['T1w_CSA']
    y_T2w = df['T2w_CSA']
    p_in = 0.25 # to check
    p_out = 0.25 # To check
    compute_regression_CSA(x, y_T1w, p_in, p_out, "T1w_CSA")
    compute_regression_CSA(x, y_T2w, p_in, p_out, 'T2w_CSA')

if __name__ == '__main__':
    main()
