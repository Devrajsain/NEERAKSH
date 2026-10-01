NEERAKSH 🌊
AI-Powered Maritime Oil Spill Detection, Drift Prediction & Vessel Attribution
       
Smart India Hackathon 2026 | Problem Statement 26143 | Team EdgeCase
Table of Contents
- The Problem
- Our Solution
- How NEERAKSH Works
- End-to-End Workflow
- System Architecture
- AI Detection Model
- Data
- Environmental Drift Analysis
- AIS-Based Vessel Attribution
- Dashboard
- Tech Stack
- Current Status
- Validation Results
- What Makes NEERAKSH Different
- Impact and Applications
- Limitations and Responsible Use
- Getting Started
- Project Links
- Roadmap
- Research and References
- Team
- Acknowledgments
The Problem
Oil Spill Response Is More Than Detection
Marine oil spills can damage ecosystems, fisheries, coastal communities and maritime operations. When a spill is detected, simply knowing its current location is not enough.
Response and investigation teams also need to understand:
- Where might the spill have originated?
- How could it have moved before satellite detection?
- Where could it move during the next 48 hours?
- Which vessels were operating near the possible source?
- How can satellite, environmental and vessel information be examined together?
Key Challenges
Challenge	Why It Matters
SAR Lookalikes	Natural ocean-surface phenomena can resemble oil spills
Unknown Spill Origin	Wind and currents can move oil away from its release location
Dynamic Spill Movement	The observed slick can continue spreading after detection
Large AIS Search Space	Many vessels may operate around the same maritime region
Fragmented Data	Satellite, environmental and vessel data are often analyzed separately
Uncertainty	Source location and future movement are estimates, not exact observations


NEERAKSH is designed to connect these stages into one maritime intelligence workflow.
Our Solution
NEERAKSH — Detect. Predict. Trace. Protect.
NEERAKSH is an AI-powered maritime intelligence platform designed to connect three major capabilities:
1. Detect
Use Sentinel-1 SAR imagery and deep learning to identify and segment potential oil-spill regions.
2. Predict
Use the detected spill location, observation time, wind and ocean-current information to estimate a possible source region and analyze potential movement over the next 48 hours.
3. Trace
Use historical AIS vessel trajectories to identify vessels whose locations and movement histories are relevant to the estimated spill origin and incident time window.
The outputs are intended to be brought together in a unified GIS-based dashboard so that users can examine the incident without manually switching between unrelated datasets.
NEERAKSH is a decision-support system. Candidate vessels are investigative leads, not automatic proof of responsibility.

How NEERAKSH Works
                    ┌─────────────────────┐
                    │  Sentinel-1 SAR     │
                    │  VV + VH Imagery    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Image Preprocessing │
                    │ Clip + Normalize    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ AI Oil Spill        │
                    │ Segmentation        │
                    │ U-Net + ResNet34    │
                    └──────────┬──────────┘
                               │
                         Spill Detected
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼
       ┌───────────────────┐       ┌───────────────────┐
       │ Origin & Drift    │       │ AIS Vessel        │
       │ Analysis          │       │ Analysis          │
       │ Wind + Currents   │       │ Position + Time   │
       │ Hindcast/Forecast │       │ Trajectory Match  │
       └─────────┬─────────┘       └─────────┬─────────┘
                 │                           │
                 └─────────────┬─────────────┘
                               ▼
                    ┌─────────────────────┐
                    │ NEERAKSH Dashboard  │
                    │ Spill • Origin      │
                    │ Trajectory • AIS    │
                    └─────────────────────┘
End-to-End Workflow
Step 1 — Satellite Observation
Acquire Sentinel-1 SAR imagery for the maritime region under investigation.
Step 2 — Preprocessing
Prepare the VV and VH channels for model inference. During model development, backscatter values were clipped to [-30, 0] dB, normalized to [0, 1], and processed as 256 × 256 patches.
Step 3 — AI-Based Detection
The U-Net + ResNet34 model produces a pixel-level probability map and segmentation mask for potential oil-spill regions.
Step 4 — Geographic Interpretation
Where georeferenced imagery is available, detected regions are associated with geographic coordinates and the satellite observation timestamp.
Step 5 — Origin and Drift Analysis
Environmental information such as ocean currents and wind is used to analyze the possible source region and potential movement of the spill.
Step 6 — 48-Hour Forecast
The proposed trajectory workflow generates potential spill positions at +6h, +12h, +24h and +48h.
Step 7 — Historical AIS Analysis
Historical vessel positions and movement histories are examined around the estimated source region and relevant time window.
Step 8 — Spatial-Temporal Matching
Vessel trajectories are compared against the estimated origin and incident timing to identify potentially relevant candidate vessels.
Step 9 — Unified Visualization
The results are presented through the NEERAKSH dashboard for human review and response planning.
System Architecture
┌────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                            │
│ Sentinel-1 SAR │ Ocean Currents │ Wind │ Historical AIS   │
└───────────────────────────┬────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                  AI DETECTION LAYER                        │
│ Preprocessing → U-Net + ResNet34 → Spill Segmentation    │
└───────────────────────────┬────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│              ENVIRONMENTAL ANALYSIS LAYER                  │
│ Source Estimation → Hindcasting → Forward Drift Forecast  │
└───────────────────────────┬────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│               MARITIME INVESTIGATION LAYER                 │
│ AIS Filtering → Spatial-Temporal Matching → Candidates    │
└───────────────────────────┬────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                 DECISION SUPPORT LAYER                     │
│ Spill │ Origin │ Trajectory │ Vessel Activity │ Dashboard │
└────────────────────────────────────────────────────────────┘
AI Detection Model
U-Net + ResNet34
The current oil-spill detection component uses a U-Net segmentation architecture with a ResNet34 encoder.
Input
- VV SAR polarization
- VH SAR polarization
Output
A pixel-level segmentation mask representing the potential oil-spill region.
Training Strategy
The model was jointly trained using:
- Oil — scenes containing oil-spill regions
- No-Oil — scenes without identified oil
- Lookalike — visually similar ocean phenomena
This training strategy is intended to reduce false positives caused by SAR lookalikes.
Loss Function
The joint model was trained using a combination of Binary Cross-Entropy (BCE) and Dice loss.
Inference
The current model uses a 0.5 probability threshold for converting the predicted probability map into a binary segmentation mask.
Data
Development Dataset
The model development dataset contains:
- 2,569 usable scenes
- 37,030 total 256 × 256 patches
- Oil, No-Oil and Lookalike categories
- Two SAR channels: VV and VH
Part I — Oil Imagery and Masks
1,200 oil images were provided; one corrupt image (00893.tif) was excluded, resulting in 1,199 usable oil scenes.
https://zenodo.org/records/8346860
Part II — No-Oil and Lookalike
- 685 No-Oil scenes
- 685 Lookalike scenes
https://zenodo.org/records/8253899
Independent Test Dataset
A separate dataset contains:
- 150 Oil scenes
- 150 No-Oil scenes
- 150 Lookalike scenes
- 450 scenes total
https://zenodo.org/records/13761290
This dataset is kept separate from model development and is intended for independent evaluation.
Note: Final independent-test metrics are not reported here because they should only be added after the current joint model has been evaluated on the complete independent test set.

Environmental Drift Analysis
From Observed Spill to Possible Origin and Future Movement
The observed satellite position is not necessarily the original spill location. Oil can be transported by ocean currents and wind before or after satellite observation.
NEERAKSH therefore includes an environmental analysis layer designed around two directions of analysis.
Backward Analysis — Hindcasting
The proposed backward workflow works from the observed spill region toward earlier positions to estimate a probable source region.
Potential inputs include:
- CMEMS ocean currents
- ERA5 wind information
- Particle-based transport modelling
- Observation timestamp
Forward Analysis — Forecasting
The proposed forward workflow uses environmental forecasts to estimate potential spill movement after detection.
Planned outputs:
Detection
   │
   ├── +6 hours
   ├── +12 hours
   ├── +24 hours
   └── +48 hours
The exact accuracy of the trajectory component depends on environmental data quality, model assumptions and validation against observed incidents.
AIS-Based Vessel Attribution
Connecting Spill Origin With Maritime Activity
After a possible source region and time window are estimated, historical AIS data can be examined to understand vessel activity around that area.
The proposed workflow includes:
1. Define the estimated source region.
2. Define a relevant incident time window.
3. Retrieve available historical AIS observations.
4. Filter vessels operating around the source region.
5. Compare vessel positions and trajectories with the estimated source.
6. Consider temporal alignment and movement behaviour.
7. Generate candidate vessels for further investigation.
Why Spatial + Temporal Matching?
Selecting the nearest vessel is not sufficient. A vessel could be close to a detected slick after the oil has already drifted away from its release location.
NEERAKSH therefore aims to connect:
Observed Spill
      ↓
Possible Origin
      ↓
Incident Time Window
      ↓
Historical Vessel Trajectory
      ↓
Candidate Vessel
The output is intended to prioritize investigation. It does not establish legal responsibility.
Dashboard
One View for the Complete Incident
The NEERAKSH dashboard is designed to combine the outputs of the different modules into a common GIS interface.
Planned/implemented visualization elements include:
- Detected spill region
- Satellite observation information
- Spill location
- Estimated origin
- Potential 48-hour trajectory
- Vessel tracks
- Candidate vessel information
- Map-based incident context
The dashboard is intended to reduce the need for manual coordination between separate satellite, environmental and AIS analysis tools.
Tech Stack
Technology	Purpose
Python	Core development and data processing
PyTorch	Deep learning
Segmentation Models PyTorch	U-Net implementation
U-Net	Pixel-level segmentation
ResNet34	Encoder/backbone
Sentinel-1 SAR	Oil-spill observation
VV + VH	SAR input channels
Raster/geospatial tools	Satellite and spatial processing
CMEMS	Ocean-current information
ERA5	Historical/reanalysis wind information
GFS	Forecast wind information where integrated
AIS	Vessel movement information
OpenDrift / OpenOil	Proposed particle-based drift and oil-weathering modelling
GIS / Web Mapping	Incident visualization
Hugging Face	Public model checkpoint hosting


Current Status
Completed
- Sentinel-1 VV/VH SAR oil-spill detection pipeline
- Joint Oil / No-Oil / Lookalike model training
- U-Net + ResNet34 segmentation model
- 256 × 256 patch-based inference pipeline
- Publicly hosted trained detection checkpoint
- Prototype visualization/dashboard work
- Independent 450-scene dataset prepared for evaluation
In Development / Proposed Integration
- Full environmental hindcasting and 48-hour forecasting pipeline
- Uncertainty-aware trajectory estimation
- Historical AIS integration
- Bayesian vessel attribution
- End-to-end dashboard integration
- Live inference/API deployment
This distinction is intentional: the trained detection model is an established component, while the broader environmental and vessel-attribution workflow requires further implementation and validation.
Validation Results
Joint Validation Performance
The best recorded validation checkpoint achieved:
Metric	Result
IoU	69.42%
Dice	81.95%
Precision	81.70%
Recall	82.20%
False Positive Rate	1.40%


These are validation results for the joint oil-spill detection model. They should not be interpreted as end-to-end NEERAKSH performance or as independent test results.
What Makes NEERAKSH Different
1. Detection Beyond Dark Pixels
The model is trained on Oil, No-Oil and Lookalike scenes rather than treating every dark SAR region as oil.
2. Detection-to-Investigation Workflow
The system is designed to connect:
Satellite Detection → Origin Estimation → Drift Analysis → AIS Investigation
3. Dual-Polarization SAR
Both VV and VH channels are used as model inputs.
4. Spatial-Temporal Vessel Analysis
The proposed vessel module considers both where a vessel was and when it was there.
5. Uncertainty-Aware Direction
The broader architecture is designed to represent uncertainty in source estimation and trajectory modelling rather than presenting every forecast as an exact path.
6. Human-in-the-Loop Decision Support
NEERAKSH is designed to assist experts rather than automatically assign responsibility to a vessel.
Impact and Applications
Maritime Authorities
Support incident assessment by combining satellite observations, environmental conditions and vessel activity.
Coast Guard and Response Teams
Provide a common view of potential spills and their possible movement.
Environmental Agencies
Help identify areas that may require monitoring or response.
Port Authorities
Support review of maritime activity around a suspected pollution incident.
Research and Monitoring
Provide a foundation for further research into SAR oil-spill detection, ocean drift modelling and maritime data analysis.
Long-Term Vision
- Wider maritime and coastal monitoring
- Multi-satellite integration
- Improved uncertainty estimation
- Near-real-time detection
- Automated incident reporting
- Stronger integration with operational AIS and environmental feeds
Limitations and Responsible Use
NEERAKSH is intended as a decision-support system and should be interpreted accordingly.
Satellite Detection
SAR lookalikes can resemble oil spills. AI predictions should be reviewed before operational action.
Geospatial Metadata
Physical spill area and geographic coordinates require appropriate georeferenced satellite data. Dataset images without geospatial metadata cannot by themselves establish real-world latitude/longitude.
Drift Forecasting
Spill movement depends on environmental conditions, model assumptions and data quality. Forecasts should therefore be treated as estimates.
AIS Data
AIS records may contain gaps or missing observations. A vessel's presence near a suspected spill source does not prove that the vessel caused the incident.
Investigation
NEERAKSH can prioritize information for review, but final attribution requires appropriate evidence, domain expertise and formal investigation.
Getting Started
Trained Model
The trained detection checkpoint is publicly available here:
https://huggingface.co/goyalharshit18/Neeraksh-oil-detection
Load the Trained Model
import torch
import segmentation_models_pytorch as smp
from huggingface_hub import hf_hub_download

device = "cuda" if torch.cuda.is_available() else "cpu"

path = hf_hub_download(
    repo_id="goyalharshit18/Neeraksh-oil-detection",
    filename="best_joint_unet_resnet34.pth"
)

model = smp.Unet(
    encoder_name="resnet34",
    encoder_weights=None,
    in_channels=2,
    classes=1,
    activation=None
).to(device)

checkpoint = torch.load(
    path,
    map_location=device,
    weights_only=True
)

model.load_state_dict(
    checkpoint.get("model_state_dict", checkpoint)
)

model.eval()
Inference Requirements
The model expects two-channel Sentinel-1 SAR input:
Channel 0 → VV
Channel 1 → VH
During model development, inputs were clipped to [-30, 0] dB and normalized to [0, 1]. For a production pipeline, preprocessing must match the training configuration.
Project Links
Resource	Link
GitHub Repository	https://github.com/Devrajsain/Spill_Tracker
Trained Model	https://huggingface.co/goyalharshit18/Neeraksh-oil-detection
Oil Dataset	https://zenodo.org/records/8346860
No-Oil + Lookalike Dataset	https://zenodo.org/records/8253899
Independent Test Dataset	https://zenodo.org/records/13761290
Copernicus Data Space	https://dataspace.copernicus.eu/


Roadmap
Phase 1 — AI Detection
- [x] Sentinel-1 SAR preprocessing
- [x] VV/VH two-channel input
- [x] U-Net + ResNet34 model
- [x] Oil / No-Oil / Lookalike joint training
- [x] Validation evaluation
- [x] Public model hosting
Phase 2 — Geospatial Intelligence
- [ ] Robust georeferenced inference pipeline
- [ ] Automated spill-area calculation
- [ ] Geographic spill localization
- [ ] Observation-time integration
Phase 3 — Drift Intelligence
- [ ] Backward source estimation
- [ ] Forward 48-hour trajectory modelling
- [ ] Environmental forecast integration
- [ ] Uncertainty regions and confidence visualization
- [ ] Validation against observed spill movement
Phase 4 — Vessel Attribution
- [ ] Historical AIS integration
- [ ] Spatial-temporal vessel filtering
- [ ] Candidate vessel scoring
- [ ] Bayesian attribution research integration
- [ ] Investigation-oriented evidence view
Phase 5 — Operational Platform
- [ ] Live inference service
- [ ] Automated satellite ingestion
- [ ] Updated environmental feeds
- [ ] Incident alerts
- [ ] Report generation
- [ ] Scalable deployment
Research and References
SAR Oil-Spill Detection
Research on SAR oil-spill detection highlights the difficulty of separating oil slicks from visually similar natural ocean phenomena.
NEERAKSH approach: Joint training on Oil, No-Oil and Lookalike scenes.
Bayesian Spill-Source Estimation
Research on spill-source estimation highlights uncertainty in reconstructing an unknown release location.
NEERAKSH approach: Use this research direction as a foundation for uncertainty-aware source localization and trajectory analysis.
SAR-AIS Vessel Tracing
Research on vessel tracing shows that the vessel location at satellite observation time may differ from its location at the time of discharge.
NEERAKSH approach: Connect estimated spill origin and incident time with historical AIS movement rather than simply selecting the nearest vessel.
Team
Team EdgeCase
Smart India Hackathon 2026
Problem Statement: 26143
PS: Leveraging satellite imagery to determine oil spills at sea along with AIS data correlations to identify vessel responsible for the spill.
Add the final registered team-member roster and individual responsibilities here before publishing the repository if required.
Acknowledgments
NEERAKSH builds upon open satellite, geospatial, oceanographic and machine-learning ecosystems.
We acknowledge:
- Copernicus Sentinel-1 for SAR satellite observations
- Copernicus Marine Service (CMEMS) for oceanographic data
- ECMWF / ERA5 for atmospheric reanalysis data
- NOAA / GFS for forecast weather data where applicable
- Zenodo for the oil-spill datasets
- PyTorch for deep-learning infrastructure
- Segmentation Models PyTorch for segmentation architecture support
- OpenDrift / OpenOil for proposed particle-based drift and oil-weathering modelling
- Hugging Face for public model hosting
License
Add the license selected for the NEERAKSH repository here before publishing. Do not claim a specific license unless it has been formally selected for this repository.
NEERAKSH
Detect. Predict. Trace. Protect.
From satellite observation to maritime intelligence.
