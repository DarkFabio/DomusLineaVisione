# Documentazione Tecnica — Tiles Vision (Conteggio Pezzi Uscita Forno)

## 1. Panoramica del Sistema
**Tiles Vision** è un sistema di visione artificiale 2D/3D (basato su Intel RealSense e segmentazione YOLO) progettato per il conteggio e il controllo qualità delle piastrelle all'uscita del forno.

Il sistema esegue in parallelo:
1. **Rilevamento e classificazione:** Segmenta ogni piastrella nell'inquadratura, distingue quelle integre da quelle rotte/scheggiate tramite criteri geometrici e raggruppa i pezzi in file trasversali.
2. **Conteggio e integrazione PLC:** Quando una fila attraversa la zona di conteggio, legge i dati di formato e cadenza dal PLC Omron (via EtherNet/IP) e registra l'evento su database.
3. **Interfaccia Operatore e Analisi Storica:** Espone una dashboard web (Gradio) con video live annotato, diagnostica in tempo reale e grafici storici a barre (volumi) e a linee (continuità di marcia e rilevamento buchi di produzione).

---

## 2. Struttura dei File

| File | Classe / Ruolo | Responsabilità Principali |
| :--- | :--- | :--- |
| **`main.py`** *(App principale)* | Orchestratore & UI Web (`Gradio`) | Costruisce l'interfaccia web, gestisce i 4 timer asincroni, comunica con il PLC Omron (`aphyt`) e coordina il salvataggio eventi. |
| **`camera.py`** | `VideoCamera` | Gestisce la camera Intel RealSense (incluso auto-recovery USB), esegue l'inferenza YOLO (`best.engine` / `best.pt`), classifica i pezzi, raggruppa le file e gestisce il trigger di conteggio. |
| **`DataLogger.py`** | `DataLogger` | Gestisce la connessione SQLite (`history.db`), le query temporali, il cambio unità (`pz` / `m²`) e la generazione dei grafici Plotly a barre e a linee. |
| **`config.yaml`** | Configurazione a caldo | Contiene parametri UI, soglie di visione, coordinate zona di conteggio e IP del PLC. Viene ricaricato ogni 5 secondi senza riavviare il programma. |
| **`history.db`** | Database `SQLite` | Persistenza locale degli eventi di produzione nella tabella `production_events`. |

---

## 3. Pipeline di Visione e Classificazione (`camera.py`)

### A. Acquisizione e Auto-Recovery Hardware
* Il sistema utilizza una camera **Intel RealSense** configurata a `1280x720 @ 30 FPS` (`bgr8`).
* **Perché il reset hardware (`reset_camera` / `recover_camera`):** In ambiente industriale, disturbi elettrici o cali sul bus USB possono bloccare lo stream video. Se la lettura dei frame fallisce o la camera risulta disconnessa, la classe invia automaticamente un comando `device.hardware_reset()`, attende 5 secondi per la rinegoziazione USB e riavvia la pipeline senza richiedere l'intervento dell'operatore.

### B. Inferenza AI e Filtro Geometrico (`extract_objects` & `classify_tiles`)
* **Modello:** Carica `best.engine` (TensorRT ottimizzato per GPU NVIDIA) se presente, altrimenti ripiega su `best.pt`.
* **Perché la mediana come riferimento (`np.median`):** Anziché cablare le dimensioni in pixel del formato (che cambiano ad ogni cambio produzione), il sistema calcola a ogni frame l'**area mediana** (`self.reference_area`) di tutte le piastrelle rilevate nell'inquadratura.
* **Criteri di validità (`valid = True/False`):** Una piastrella viene classificata come **Buona** (verde) solo se rispetta due condizioni simultanee; altrimenti viene scartata come **Rotta** (rossa):
  1. **Tolleranza d'area:** L'area in pixel rientra nell'intervallo `[Area_ref * (1 - min_area_percentage), Area_ref * (1 + max_area_percentage)]`.
  2. **Rettangolarità (`min_rect_ratio`):** Il rapporto tra l'area reale del contorno e l'area del minimo rettangolo circoscritto (`cv2.minAreaRect`) deve essere ≥ 0.85. Questo permette di scartare pezzi scheggiati o spezzati che avessero comunque un'area vicina a quella nominale.

### C. Raggruppamento in File e Logica di Trigger (`find_rows` & `update_counter`)
* **Raggruppamento (`find_rows`):** I centri di massa (`cy`) delle piastrelle vengono ordinati verticalmente e aggregati nella stessa fila se distano meno di `100 px` dalla coordinata media `mean_y` della fila (scartando falsi positivi con meno di 2 pezzi).
* **Zona di conteggio (`count_area_top` -> `count_area_bottom`):** Quando la `mean_y` di una fila entra nella fascia gialla configurata (es. tra `550 px` e `680 px`), scatta il conteggio.
* **Anti-rimbalzo (`row_counted` + `count_lock_time`):** Per evitare doppi conteggi della stessa fila mentre attraversa la zona (o per oscillazioni del rullo), il trigger si arma (`self.row_counted = True`), blocca nuovi conteggi per `count_lock_time` (1.0s) e si riarma solo quando nessuna fila è più presente nella fascia.

---

## 4. Integrazione PLC e Salvataggio Dati (`main.py` & `history.db`)

L'interfaccia Gradio orchestra 4 timer indipendenti per mantenere fluida la UI a 30 FPS senza bloccaggi dovuti a rete o disco:
* `timer_camera` (`0.03s`): Inferenza e rendering video.
* `timer_database` (`1.0s`): Controllo eventi e scrittura su DB.
* `timer_config` (`5.0s`): Ricarica a caldo di `config.yaml`.
* `timer_grafico` (`10.0s`): Aggiornamento automatico dei grafici.

Quando `camera.last_event` è valorizzato, `salva_eventi()` interroga il PLC Omron (`omron.NSeries` all'IP `192.168.250.1`) e salva una riga in `production_events`:

| Colonna DB | Origine | Descrizione |
| :--- | :--- | :--- |
| `timestamp` | Automatico (SQLite/Pandas) | Data e ora esatta del passaggio della fila. |
| `tiles_row` | PLC (`pc_pezzi_per_fila`) | Numero teorico di pezzi attesi per ogni fila. |
| `good_tiles` | Visione (`camera.last_event`) | Numero di piastrelle integre rilevate nella fila. |
| `broken_tiles` | Visione (`camera.last_event`) | Numero di piastrelle rotte/scartate rilevate nella fila. |
| `area_tiles` | PLC (`pc_area_tile`) | Superficie della singola piastrella in m². |
| `periodo_carico` | PLC (`pc_minimo_periodo_carico_materiale`) | Tempo ciclo nominale di carico del forno (in secondi). |

---

## 5. Analisi Grafica e Rilevamento Buchi (`DataLogger.py`)

Il sistema supporta la commutazione istantanea tra **pezzi (`pz`)** e **metri quadri (`m²`)** (moltiplicando i conteggi per `area_tiles` a runtime senza alterare i dati grezzi nel DB) e offre due modalità di visualizzazione:

### 1. Grafico a Barre (Analisi Volumi)
* Raggruppa i record in *bucket* temporali fissi (`5 min` su *Ultima ora*, `1 ora` su *Oggi*, `1 giorno` su *7/30 Giorni*) sommandone i valori (`groupby().sum()`).
* Gli intervalli senza produzione vengono riempiti con `0` (`reindex`) per garantire continuità sull'asse X.

### 2. Grafico a Linee (Continuità e Buchi di Produzione)
* **Perché non usare le somme:** Sommare i pezzi su finestre temporali nasconde le micro-fermate e le irregolarità di alimentazione del forno.
* **Algoritmo ad onda quadra su record singoli:**
  1. I record vengono ordinati cronologicamente su un asse X temporale reale (`type="date"`) bloccato sull'esatta finestra selezionata (`range=[dt_inizio, dt_fine]`).
  2. Per ogni record si calcola il tempo trascorso dal precedente (`delta_s = timestamp.diff()`) e lo si confronta con una soglia dinamica pari a `periodo_carico * 1.3` (+30% di tolleranza rispetto alla velocità impostata sul PLC).
  3. **Iniezione degli zeri:** Se `delta_s` supera la soglia, viene rilevato un buco di produzione e vengono inseriti due punti virtuali a `0` (uno al termine del ciclo del pezzo precedente `t_prev + periodo_carico`, l'altro 1 secondo prima della ripartenza).
  4. **Chiusura ai bordi:** La stessa verifica viene eseguita tra `dt_inizio` e il primo record e tra l'ultimo record e `dt_fine`, assicurando che la linea parta da zero e scenda a zero se il forno è fermo agli estremi dell'intervallo osservato.

---

## 6. Guida Rapida alla Taratura (`config.yaml`)
* **`min_confidence` (`0.50`):** Soglia minima di confidenza del modello YOLO per considerare valida una maschera.
* **`min_area_percentage` (`0.25`) / `max_area_percentage` (`1.0`):** Scarto percentuale ammesso rispetto all'area mediana della fila (es. `0.25` = scarta pezzi più piccoli del 75% della mediana).
* **`min_rect_ratio` (`0.85`):** Fattore di forma rettangolare (abbassare leggermente se gli angoli smussati o le ombre causano falsi scarti).
* **`count_area_top` (`550`) / `count_area_bottom` (`680`):** Posizione verticale in pixel della fascia gialla di conteggio.
* **`count_lock_time` (`1.0`):** Tempo minimo in secondi tra due conteggi consecutivi.

---
