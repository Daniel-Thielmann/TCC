import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import numpy as np
from tqdm import tqdm
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis as QDA

from methods.pipelines.fbcsp_fractal import run_fbcsp_fractal


def run_all():
    all_rows = []

    for subject_id in tqdm(range(1, 10), desc="FBCSP + Fractal"):
        rows = run_fbcsp_fractal(subject_id)
        df = pd.DataFrame(rows)

        # ========= APLICA MELHORIAS AQUI ========= #

        features = df[["left_prob", "right_prob"]].values
        X_feat = StandardScaler().fit_transform(features)

        # Elimina colinearidade (sem warnings) via PCA(1)
        X_feat = PCA(n_components=1).fit_transform(X_feat)
        y = df["true_label"].values

        clf = QDA(reg_param=0.1)  # QDA robusto
        clf.fit(X_feat, y)
        probs = clf.predict_proba(X_feat)

        df["left_prob"] = probs[:, 0]
        df["right_prob"] = probs[:, 1]

        # ========================================= #

        os.makedirs("results/FBCSP_Fractal/Training", exist_ok=True)
        df.to_csv(f"results/FBCSP_Fractal/Training/P{subject_id:02d}.csv", index=False)
        all_rows.append(df)

    return pd.concat(all_rows, ignore_index=True)


if __name__ == "__main__":
    df = run_all()
    df["correct_prob"] = df.apply(
        lambda row: row["left_prob"] if row["true_label"] == 1 else row["right_prob"],
        axis=1,
    )
    acc = (df["true_label"] == df["left_prob"].lt(0.5).astype(int) + 1).mean()
    mean_prob = df["correct_prob"].mean()
    total = len(df)
    counts = dict(df["true_label"].value_counts().sort_index())

    print(
        f"Acurácia: {acc:.4f} | Média Prob. Correta: {mean_prob:.4f} | Amostras: {total} | Rótulos: {counts}"
    )
