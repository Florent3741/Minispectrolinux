import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import time
import csv
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

LONGUEURS_ONDE = [415, 445, 480, 515, 555, 590, 630, 680]
COULEURS_SPECTRE = ['#610061', '#001aff', '#00aaff', '#00ff55', '#aaff00', '#ffaa00', '#ff3300', '#990000']

class MiniSpectroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Spectro - Physique-Chimie")
        self.root.geometry("1000x680")
        self.root.configure(bg="#7f7f7f")

        self.ser = None
        self.lambda_choisie = 555
        self.cinetique_en_cours = False
        
        self.spectre_abs = []
        self.beer_c = []
        self.beer_abs = []
        self.cinetique_t = []
        self.cinetique_abs = []

        self.creer_interface()
        self.root.after(500, self.connexion_auto)

    def creer_interface(self):
        header = tk.Frame(self.root, bg="#7f7f7f", highlightbackground="white", highlightthickness=2)
        header.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        tk.Label(header, text="Mini Spectro", font=("Arial", 22, "bold"), bg="#7f7f7f", fg="#f39c12").pack(side=tk.LEFT, padx=20, pady=10)

        conn_frame = tk.Frame(header, bg="#7f7f7f")
        conn_frame.pack(side=tk.RIGHT, padx=15)
        
        self.lbl_etat_usb = tk.Label(conn_frame, text="● Non connecté", font=("Arial", 10, "bold"), bg="#7f7f7f", fg="#ffcccc")
        self.lbl_etat_usb.pack(side=tk.LEFT, padx=10)

        self.btn_connect = tk.Button(conn_frame, text="Reconnecter l'appareil", command=self.connexion_auto, bg="#2ecc71", fg="white", font=("Arial", 10, "bold"))
        self.btn_connect.pack(side=tk.LEFT, padx=5)

        main_frame = tk.Frame(self.root, bg="#7f7f7f")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        menu_frame = tk.Frame(main_frame, bg="#6e6e6e", highlightbackground="white", highlightthickness=1, width=320)
        menu_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        menu_frame.pack_propagate(False)

        boutons = [
            ("1. Réglage du zéro", self.faire_blanc, 0, 0),
            ("Spectre d'absorption", self.afficher_spectre, 0, 1),
            ("Choisir la longueur\nd'onde", self.choisir_lambda, 1, 0),
            ("Mesure de\nl'absorbance", self.mesurer_absorbance, 1, 1),
            ("Loi de\nBeer-Lambert", self.mode_beer_lambert, 2, 0),
            ("Cinétique", self.mode_cinetique, 2, 1),
        ]

        for texte, cmd, r, c in boutons:
            f = tk.Frame(menu_frame, bg="#6e6e6e")
            f.grid(row=r, column=c, padx=12, pady=18)
            btn = tk.Button(f, text="●", font=("Arial", 24), width=3, height=1, bg="#3498db", fg="white",
                            activebackground="#2980b9", relief=tk.RAISED, bd=3, command=cmd)
            btn.pack()
            tk.Label(f, text=texte, bg="#6e6e6e", fg="white", font=("Arial", 9, "bold"), justify=tk.CENTER).pack(pady=(5, 0))

        self.work_frame = tk.Frame(main_frame, bg="white", highlightbackground="white", highlightthickness=1)
        self.work_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.afficher_accueil()

        info_frame = tk.Frame(self.root, bg="white", highlightbackground="#f39c12", highlightthickness=3)
        info_frame.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        tk.Label(info_frame, text="ℹ", font=("Arial", 18, "bold"), bg="#f39c12", fg="white", width=3).pack(side=tk.LEFT, fill=tk.Y)
        self.lbl_info = tk.Label(info_frame, text="Recherche automatique du spectrophotomètre...",
                                 font=("Arial", 10), bg="white", fg="#2c3e50", anchor="w", padx=10, pady=8)
        self.lbl_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        status_bar = tk.Frame(self.root, bg="#34495e")
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.lbl_lambda = tk.Label(status_bar, text=f"Longueur d'onde sélectionnée : λ = {self.lambda_choisie} nm",
                                   bg="#34495e", fg="white", font=("Arial", 9, "bold"), padx=10, pady=3)
        self.lbl_lambda.pack(side=tk.LEFT)

    def nettoyer_zone_travail(self):
        self.cinetique_en_cours = False
        for widget in self.work_frame.winfo_children():
            widget.destroy()

    def afficher_accueil(self):
        self.nettoyer_zone_travail()
        tk.Label(self.work_frame, text="Protocole d'utilisation", font=("Arial", 16, "bold"), bg="white", fg="#2c3e50").pack(pady=(60, 20))
        etapes = (
            "Étape 1 : Placer une cuve remplie d'eau distillée (le blanc) dans l'appareil.\n\n"
            "Étape 2 : Cliquer sur « 1. Réglage du zéro ».\n\n"
            "Étape 3 : Remplacer la cuve par la solution colorée à étudier.\n\n"
            "Étape 4 : Choisir le mode souhaité (Spectre, Absorbance, Beer-Lambert ou Cinétique)."
        )
        tk.Label(self.work_frame, text=etapes, font=("Arial", 11), bg="white", fg="#333333", justify=tk.LEFT).pack(pady=10, padx=30)

    def connexion_auto(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

        ports = serial.tools.list_ports.comports()
        port_arduino = None
        for p in ports:
            if "ACM" in p.device or "USB" in p.device or "Arduino" in p.description:
                port_arduino = p.device
                break

        if not port_arduino:
            self.lbl_etat_usb.config(text="● Appareil non détecté", fg="#ffcccc")
            self.lbl_info.config(text="Branchez le câble USB du spectrophotomètre puis cliquez sur « Reconnecter l'appareil ».")
            return

        try:
            self.lbl_info.config(text=f"Connexion sur {port_arduino} et calibration de la LED en cours...")
            self.root.update()
            self.ser = serial.Serial(port_arduino, 9600, timeout=5)
            self.ser.readline()
            self.lbl_etat_usb.config(text=f"● Connecté ({port_arduino})", fg="#aaffaa")
            self.lbl_info.config(text="Appareil prêt ! Insérez la cuve d'eau distillée et cliquez sur « 1. Réglage du zéro ».")
            self.envoyer_commande(f"{self.lambda_choisie} nm")
        except Exception as e:
            self.lbl_etat_usb.config(text="● Erreur USB", fg="#ffcccc")
            messagebox.showerror("Erreur USB", f"Impossible d'accéder au port {port_arduino}.\nVérifiez le branchement.\n({e})")

    def envoyer_commande(self, cmd):
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("Non connecté", "L'appareil n'est pas connecté. Vérifiez le câble USB et cliquez sur 'Reconnecter'.")
            return None
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\n").encode('utf-8'))
        return True

    def faire_blanc(self):
        if not self.envoyer_commande("blanc"): return
        self.lbl_info.config(text="Mesure du blanc en cours... Ne touchez pas à la cuve.")
        self.root.update()
        while True:
            ligne = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if ligne == "A" or ligne == "":
                break
        self.lbl_info.config(text="Réglage du zéro terminé ! Vous pouvez insérer votre solution colorée.")
        messagebox.showinfo("Réglage du zéro", "Le zéro a été effectué avec succès.")

    def afficher_spectre(self):
        if not self.envoyer_commande("spectre"): return
        self.lbl_info.config(text="Mesure du spectre en cours...")
        self.root.update()

        ligne = self.ser.readline().decode('utf-8', errors='ignore').strip()
        try:
            valeurs = [int(x) / 1000.0 for x in ligne.split()]
            if len(valeurs) != 8: raise ValueError
            self.spectre_abs = valeurs
        except Exception:
            self.lbl_info.config(text="Erreur lors de la mesure du spectre. Recommencez.")
            return

        self.nettoyer_zone_travail()
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        ax.plot(LONGUEURS_ONDE, self.spectre_abs, '-o', color='#2c3e50', linewidth=2)
        for l, a, c in zip(LONGUEURS_ONDE, self.spectre_abs, COULEURS_SPECTRE):
            ax.plot(l, a, 'o', color=c, markersize=10)
            
        ax.set_title("Spectre d'absorption A = f(λ)")
        ax.set_xlabel("Longueur d'onde λ (nm)")
        ax.set_ylabel("Absorbance A")
        ax.set_xticks(LONGUEURS_ONDE)
        ax.grid(True, linestyle='--', alpha=0.6)

        canvas = FigureCanvasTkAgg(fig, master=self.work_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tk.Button(self.work_frame, text="Enregistrer les données (.csv)", command=lambda: self.exporter_csv(
            ["Longueur_onde_nm", "Absorbance"], zip(LONGUEURS_ONDE, self.spectre_abs)), bg="#3498db", fg="white").pack(pady=5)
        
        max_idx = int(np.argmax(self.spectre_abs))
        self.lbl_info.config(text=f"Maximum d'absorption détecté à λ = {LONGUEURS_ONDE[max_idx]} nm (A = {self.spectre_abs[max_idx]:.3f}).")

    def choisir_lambda(self):
        fen = tk.Toplevel(self.root)
        fen.title("Choix de λ")
        fen.geometry("300x150")
        tk.Label(fen, text="Sélectionnez la longueur d'onde :", font=("Arial", 10)).pack(pady=10)
        
        cb = ttk.Combobox(fen, values=[f"{l} nm" for l in LONGUEURS_ONDE], state="readonly")
        cb.set(f"{self.lambda_choisie} nm")
        cb.pack(pady=5)

        def valider():
            choix = cb.get()
            self.lambda_choisie = int(choix.split()[0])
            self.lbl_lambda.config(text=f"Longueur d'onde sélectionnée : λ = {self.lambda_choisie} nm")
            self.envoyer_commande(choix)
            self.lbl_info.config(text=f"Longueur d'onde réglée sur {choix}.")
            fen.destroy()

        tk.Button(fen, text="Valider", command=valider, bg="#2ecc71", fg="white").pack(pady=10)

    def mesurer_absorbance(self):
        if not self.envoyer_commande("absorbance"): return
        ligne = self.ser.readline().decode('utf-8', errors='ignore').strip()
        try:
            abs_val = int(ligne) / 1000.0
        except ValueError:
            self.lbl_info.config(text="Erreur de lecture.")
            return

        self.nettoyer_zone_travail()
        tk.Label(self.work_frame, text=f"Mesure à λ = {self.lambda_choisie} nm", font=("Arial", 14), bg="white").pack(pady=(80, 10))
        tk.Label(self.work_frame, text=f"A = {abs_val:.3f}", font=("Arial", 36, "bold"), bg="white", fg="#e67e22").pack(pady=20)
        self.lbl_info.config(text=f"Absorbance mesurée : {abs_val:.3f} à {self.lambda_choisie} nm.")

    def mode_beer_lambert(self):
        self.nettoyer_zone_travail()
        self.beer_c = []
        self.beer_abs = []

        ctrl = tk.Frame(self.work_frame, bg="white")
        ctrl.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(ctrl, text="Concentration C :", bg="white").pack(side=tk.LEFT)
        ent_c = tk.Entry(ctrl, width=12)
        ent_c.pack(side=tk.LEFT, padx=5)

        fig, ax = plt.subplots(figsize=(5.5, 3.8), dpi=100)
        canvas = FigureCanvasTkAgg(fig, master=self.work_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10)

        def ajouter_point():
            try:
                c = float(ent_c.get().replace(',', '.'))
            except ValueError:
                messagebox.showerror("Erreur", "Entrez une valeur numérique pour la concentration.")
                return
            if not self.envoyer_commande("absorbance"): return
            ligne = self.ser.readline().decode('utf-8', errors='ignore').strip()
            try:
                a = int(ligne) / 1000.0
            except ValueError:
                return

            self.beer_c.append(c)
            self.beer_abs.append(a)
            ent_c.delete(0, tk.END)
            tracer()

        def tracer():
            ax.clear()
            ax.plot(self.beer_c, self.beer_abs, 'bo', label="Mesures")
            if len(self.beer_c) >= 2:
                k, b = np.polyfit(self.beer_c, self.beer_abs, 1)
                x_vals = np.linspace(0, max(self.beer_c), 50)
                ax.plot(x_vals, k * x_vals + b, 'r--', label=f"Modèle : A = {k:.2f}·C + {b:.3f}")
                ax.legend()
            ax.set_title(f"Étalonnage Beer-Lambert (λ = {self.lambda_choisie} nm)")
            ax.set_xlabel("Concentration C")
            ax.set_ylabel("Absorbance A")
            ax.grid(True, linestyle='--', alpha=0.6)
            canvas.draw()

        tk.Button(ctrl, text="Mesurer & Ajouter", command=ajouter_point, bg="#2ecc71", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl, text="Enregistrer (.csv)", command=lambda: self.exporter_csv(
            ["Concentration", "Absorbance"], zip(self.beer_c, self.beer_abs)), bg="#3498db", fg="white").pack(side=tk.RIGHT)
        self.lbl_info.config(text="Saisissez la concentration de la solution étalon puis cliquez sur 'Mesurer & Ajouter'.")

    def mode_cinetique(self):
        self.nettoyer_zone_travail()
        self.cinetique_t = []
        self.cinetique_abs = []

        ctrl = tk.Frame(self.work_frame, bg="white")
        ctrl.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(ctrl, text="Intervalle (s) :", bg="white").pack(side=tk.LEFT)
        ent_dt = tk.Entry(ctrl, width=6)
        ent_dt.insert(0, "5")
        ent_dt.pack(side=tk.LEFT, padx=5)

        fig, ax = plt.subplots(figsize=(5.5, 3.8), dpi=100)
        canvas = FigureCanvasTkAgg(fig, master=self.work_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10)

        def boucle_acquisition(dt):
            t0 = time.time()
            while self.cinetique_en_cours:
                t_courant = round(time.time() - t0, 1)
                if self.ser and self.ser.is_open:
                    self.ser.reset_input_buffer()
                    self.ser.write(b"absorbance\n")
                    ligne = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    try:
                        a = int(ligne) / 1000.0
                        self.cinetique_t.append(t_courant)
                        self.cinetique_abs.append(a)
                        self.root.after(0, maj_graph)
                    except ValueError:
                        pass
                time.sleep(dt)

        def maj_graph():
            ax.clear()
            ax.plot(self.cinetique_t, self.cinetique_abs, 'g-o', markersize=4)
            ax.set_title(f"Suivi cinétique (λ = {self.lambda_choisie} nm)")
            ax.set_xlabel("Temps t (s)")
            ax.set_ylabel("Absorbance A")
            ax.grid(True, linestyle='--', alpha=0.6)
            canvas.draw()

        def demarrer():
            if self.cinetique_en_cours: return
            try:
                dt = max(1.5, float(ent_dt.get()))
            except ValueError:
                return
            self.cinetique_en_cours = True
            self.lbl_info.config(text="Acquisition cinétique en cours...")
            threading.Thread(target=boucle_acquisition, args=(dt,), daemon=True).start()

        def arreter():
            self.cinetique_en_cours = False
            self.lbl_info.config(text="Suivi cinétique arrêté.")

        tk.Button(ctrl, text="▶ Démarrer", command=demarrer, bg="#2ecc71", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl, text="■ Arrêter", command=arreter, bg="#e74c3c", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl, text="Enregistrer (.csv)", command=lambda: self.exporter_csv(
            ["Temps_s", "Absorbance"], zip(self.cinetique_t, self.cinetique_abs)), bg="#3498db", fg="white").pack(side=tk.RIGHT)
        self.lbl_info.config(text="Cliquez sur 'Démarrer' pour suivre l'absorbance au cours du temps.")

    def exporter_csv(self, entetes, lignes):
        fichier = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("Fichier CSV", "*.csv")])
        if not fichier: return
        with open(fichier, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(entetes)
            writer.writerows(lignes)
        messagebox.showinfo("Export", "Fichier enregistré. Vous pouvez l'ouvrir avec LibreOffice Calc.")

if __name__ == "__main__":
    root = tk.Tk()
    app = MiniSpectroApp(root)
    root.mainloop()
