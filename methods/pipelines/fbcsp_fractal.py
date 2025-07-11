import numpy as np
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent / "contexts"))
from contexts.BCICIV2b import bciciv2b
from bciflow.modules.sf.csp import csp
from bciflow.modules.tf.filterbank import filterbank
from methods.features.fractal import HiguchiFractalEvolution
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA


def run_fbcsp_fractal(subject_id, data_path="dataset/BCICIV2b/"):
    """
    Executa o metodo FBCSP (Filter Bank CSP) combinado com features fractais para classificacao de EEG.

    Args:
        subject_id: ID do sujeito a ser processado (1-9)
        data_path: Caminho para o diretorio com os dados

    Returns:
        Lista de dicionarios com os resultados de classificacao
    """
    dataset = bciciv2b(subject=subject_id, path=data_path)
    X = dataset["X"]
    y = np.array(dataset["y"]) + 1

    # Filtra classes 1 e 2, se necessario (BCICIV2b já retorna apenas left-hand e right-hand)
    # mask = (y == 1) | (y == 2)
    # X = X[mask]
    # y = y[mask]

    eegdata = {"X": X, "sfreq": 250}  # BCICIV2b usa 250Hz
    eegdata = filterbank(eegdata, kind_bp="chebyshevII")
    if not isinstance(eegdata, dict) or "X" not in eegdata:
        raise TypeError(
            f"Retorno inesperado de filterbank: {type(eegdata)} - {eegdata}"
        )
    X_filt = eegdata["X"]

    # Ajusta shape para CSP: [n_trials, n_bands, n_channels, n_samples]
    if X_filt.ndim == 5:
        n_trials, n_bands, n_chans, n_filters, n_samples = X_filt.shape
        X_filt = X_filt.transpose(0, 1, 3, 2, 4).reshape(
            n_trials, n_bands * n_filters, n_chans, n_samples
        )
    elif X_filt.ndim == 4:
        n_trials, n_bands, n_chans, n_samples = X_filt.shape
        # shape ja esta correto
    else:
        raise ValueError(f"Shape inesperado apos filterbank: {X_filt.shape}")

    transformer = csp()
    transformer.fit({"X": X_filt, "y": y})
    X_csp = transformer.transform({"X": X_filt})[
        "X"
    ]  # [trials, bands, components, samples]

    hfd = HiguchiFractalEvolution(kmax=100)
    features = []
    for trial in X_csp:
        trial_feat = []
        for band in trial:
            for comp in band:
                comp = comp - np.mean(comp)
                slope, mean_lk, std_lk = hfd._calculate_enhanced_hfd(comp)
                trial_feat.extend([slope, mean_lk, std_lk])
        features.append(trial_feat)
    features = np.array(features)

    features = StandardScaler().fit_transform(features)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    rows = []

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(features, y)):
        X_train, X_test = features[train_idx], features[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        clf = LDA()
        clf.fit(X_train, y_train)
        probs = clf.predict_proba(X_test)

        for i, idx in enumerate(test_idx):
            rows.append(
                {
                    "subject_id": subject_id,
                    "fold": fold_idx,
                    "true_label": y_test[i],
                    "left_prob": probs[i][0],
                    "right_prob": probs[i][1],
                }
            )

    return rows
