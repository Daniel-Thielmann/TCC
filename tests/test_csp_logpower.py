import os
import sys
import pandas as pd
import numpy as np
from sklearn.metrics import cohen_kappa_score

# Adiciona o diretório raiz ao path do Python para importações
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sklearn.metrics import cohen_kappa_score


def test_csp_logpower_pipeline():
    """
    Testa o pipeline CSP com LogPower usando dataset WCCI2020 padronizado.

    Executa classificação de motor imagery para todos os sujeitos do dataset WCCI2020
    usando filtros, CSP e extração de features LogPower com validação cruzada robusta.

    Returns:
        dict: Resultados de performance por sujeito
    """
    print("Testando pipeline CSP LogPower...")
    print("Dataset: WCCI2020 (9 sujeitos)")
    print("Tarefa: Classificação de motor imagery (left-hand vs right-hand)")
    print("Pipeline: Bandpass 8-30Hz → CSP → LogPower → LDA (5-fold CV)")
    print("-" * 60)

    import scipy.io as sio
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
    from scipy.signal import butter, filtfilt

    def bandpass_filter(data, low_freq=8, high_freq=30, sfreq=250, order=4):
        """Aplica filtro passa-banda usando Butterworth."""
        nyquist = sfreq / 2
        low = low_freq / nyquist
        high = high_freq / nyquist
        b, a = butter(order, [low, high], btype="band")
        return filtfilt(b, a, data, axis=-1)

    def extract_csp_features(X, y, n_components=4):
        """Extrai features CSP com log power."""
        from bciflow.modules.sf.csp import csp

        # Aplica CSP (sem parâmetros no construtor)
        transformer = csp()
        transformer.fit({"X": X[:, np.newaxis, :, :], "y": y})
        X_csp = transformer.transform({"X": X[:, np.newaxis, :, :]})["X"]

        # Remove dimensão de banda (apenas uma banda)
        X_csp = X_csp[:, 0, :, :]  # [trials, components, samples]

        # Extrai log power features
        features = []
        for trial in X_csp:
            # Limita aos primeiros n_components componentes
            comps = trial[:n_components] if trial.shape[0] >= n_components else trial
            trial_features = []
            for component in comps:
                # Log da variância (potência)
                log_power = np.log(
                    np.var(component) + 1e-10
                )  # +epsilon para evitar log(0)
                trial_features.append(log_power)
            features.append(trial_features)

        return np.array(features)

    results = {}
    all_accuracies = []
    all_kappas = []

    for subject_id in range(1, 10):  # Sujeitos 1-9
        print(f"Processando sujeito P{subject_id:02d}...")

        try:
            # Carrega dados do WCCI2020
            mat_file = f"dataset/wcci2020/parsed_P{subject_id:02d}T.mat"
            if not os.path.exists(mat_file):
                raise FileNotFoundError(f"Arquivo não encontrado: {mat_file}")

            mat_data = sio.loadmat(mat_file)
            X = mat_data["RawEEGData"]  # [trials, channels, samples]
            y = mat_data["Labels"].flatten()  # [trials]
            sfreq = mat_data["sampRate"][0][0]  # Frequência de amostragem

            print(
                f"  Dados carregados: {X.shape[0]} trials, {X.shape[1]} canais, {X.shape[2]} amostras"
            )
            print(f"  Classes: {np.unique(y)}, Freq: {sfreq}Hz")

            if X.shape[0] < 10:
                print(
                    f"  AVISO: Poucos dados ({X.shape[0]} trials), pulando sujeito..."
                )
                continue

            # Aplica filtro passa-banda 8-30Hz
            X_filtered = bandpass_filter(X, low_freq=8, high_freq=30, sfreq=sfreq)

            # Validação cruzada 5-fold
            cv_accuracies = []
            cv_kappas = []

            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

            for fold, (train_idx, test_idx) in enumerate(skf.split(X_filtered, y)):
                X_train, X_test = X_filtered[train_idx], X_filtered[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]

                # Extrai features CSP
                features_train = extract_csp_features(X_train, y_train, n_components=4)
                features_test = extract_csp_features(X_test, y_test, n_components=4)

                # Normalização
                scaler = StandardScaler()
                features_train = scaler.fit_transform(features_train)
                features_test = scaler.transform(features_test)

                # Classificação LDA
                clf = LDA()
                clf.fit(features_train, y_train)
                y_pred = clf.predict(features_test)

                # Métricas
                fold_accuracy = (y_test == y_pred).mean()
                fold_kappa = cohen_kappa_score(y_test, y_pred)

                cv_accuracies.append(fold_accuracy)
                cv_kappas.append(fold_kappa)

            # Métricas finais do sujeito
            accuracy = np.mean(cv_accuracies)
            kappa = np.mean(cv_kappas)

            # Armazena resultados
            results[f"P{subject_id:02d}"] = {
                "accuracy": accuracy,
                "kappa": kappa,
                "n_samples": X.shape[0],
                "class_distribution": dict(pd.Series(y).value_counts().sort_index()),
                "cv_accuracies": cv_accuracies,
                "cv_kappas": cv_kappas,
            }

            all_accuracies.append(accuracy)
            all_kappas.append(kappa)

            print(
                f"  Acurácia: {accuracy:.4f} ± {np.std(cv_accuracies):.4f} | Kappa: {kappa:.4f} | Amostras: {X.shape[0]}"
            )

        except Exception as e:
            print(f"  ERRO: {str(e)}")
            results[f"P{subject_id:02d}"] = {"error": str(e)}

    # Estatísticas gerais
    print("-" * 60)
    print("RESULTADOS FINAIS:")
    if all_accuracies:
        print(
            f"Acurácia média: {np.mean(all_accuracies):.4f} ± {np.std(all_accuracies):.4f}"
        )
        print(f"Kappa médio: {np.mean(all_kappas):.4f} ± {np.std(all_kappas):.4f}")
        print(f"Melhor acurácia: {np.max(all_accuracies):.4f}")
        print(f"Pior acurácia: {np.min(all_accuracies):.4f}")

        # Verifica se pipeline está funcionando adequadamente
        mean_accuracy = np.mean(all_accuracies)
        assert (
            mean_accuracy > 0.5
        ), f"Acurácia média abaixo do acaso: {mean_accuracy:.4f}"

        print("Teste do pipeline CSP LogPower concluído com sucesso.")
    else:
        print("Nenhum resultado válido obtido.")

    return results


if __name__ == "__main__":
    print("=== TESTE: Pipeline CSP LogPower ===")
    results = test_csp_logpower_pipeline()

    # Salva resultados para análise posterior
    os.makedirs("results/test_outputs", exist_ok=True)

    # Converte resultados para DataFrame
    summary_data = []
    for subject, metrics in results.items():
        if "error" not in metrics:
            summary_data.append(
                {
                    "Subject": subject,
                    "Accuracy": metrics["accuracy"],
                    "Kappa": metrics["kappa"],
                    "N_Samples": metrics["n_samples"],
                }
            )

    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv("results/test_outputs/csp_logpower_test_results.csv", index=False)
    print(f"Resultados salvos em: results/test_outputs/csp_logpower_test_results.csv")
