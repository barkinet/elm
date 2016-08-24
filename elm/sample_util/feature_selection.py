from functools import partial

import numpy as np
import sklearn.feature_selection as skfeat
import xarray as xr

from elm.config import import_callable
from elm.sample_util.sample_pipeline import check_array
from elm.readers import (data_arrays_as_columns,
                                       ElmStore,
                                       flatten,
                                       inverse_flatten)
from elm.model_selection.util import get_args_kwargs_defaults


@data_arrays_as_columns
def feature_selection_base(sample_x,
                          selection_dict,
                          sample_y=None,
                          keep_columns=None):
    '''feature_selection_base returns indices of columns to keep
    Params:
        sample:  a data frame sample with column names used in the
                 keyword argument "keep_columns" (see below)
        selection_dict: dict with keys /values of:
            selection: a string like
                      "sklearn.feature_selection:VarianceThreshold"
            kwargs:   init key word arguments to selection given
            scoring: scoring, if needed, passed to selection().fit
            choices:    limit the feature selection to list of column names
                        (exclude metadata columns from thresholding)
        keep_columns: columns to keep regardless of selection's selection
    Returns:
        sample_x: dataframe subset of selection's chosen columns
                   among choices
    '''
    feature_selection = selection_dict['selection']
    if feature_selection == 'all':
        return sample_x
    feature_selection_kwargs = selection_dict['kwargs']
    scoring_kwargs = selection_dict.get('scoring_kwargs') or {}
    feature_choices = selection_dict['choices']
    feature_selection = import_callable(feature_selection)
    feature_scoring = selection_dict.get('scoring')
    if feature_scoring is not None:
        if isinstance(feature_scoring, str):
            feature_scoring = getattr(skfeat, feature_scoring, None)
        else:
            feature_scoring = import_callable(selection_dict['scoring'])
        if scoring_kwargs:
            feature_scoring = partial(feature_scoring, **scoring_kwargs)
        feature_selection_args = (feature_scoring,)
    else:
        feature_selection_args = ()
    selection = feature_selection(*feature_selection_args,
                                **feature_selection_kwargs)
    if feature_choices == 'all':
        feature_choices = list(sample_x.flat.band)
    band_idx = np.array([idx for idx, band in enumerate(sample_x.flat.band)
                         if band in feature_choices])
    subset = sample_x.sample[:, band_idx]
    check_array(subset.values, 'feature_selection:{} X subset'.format(selection))

    required_args, _, _ = get_args_kwargs_defaults(selection.fit)
    if ('y' in required_args or 'Y' in required_args):
        msg = ('feature_selection [{}] requires '
               'Y data but the sample_pipeline has not '
               'positioned a {{"get_y": True}} action before '
               'feature_selection'.format(feature_selection,))
        check_array(sample_y, msg, ensure_2d=False)

    selection.fit(subset.values, y=sample_y)
    ml_columns = selection.get_support(indices=True)
    sample_x_dropped_bands =  ElmStore({'sample': xr.DataArray(sample_x.sample[:, band_idx[ml_columns]].copy(),
                                              coords=[('space', sample_x.flat.space),
                                                      ('band', sample_x.flat.band[band_idx[ml_columns]])],
                                              dims=('space','band'),
                                              attrs=sample_x.flat.attrs)},
                                          attrs=sample_x.attrs)
    del sample_x
    return sample_x_dropped_bands
