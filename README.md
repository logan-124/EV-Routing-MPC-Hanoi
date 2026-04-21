# EV Routing and Energy Management System based on Model Predictive Control (MPC)

## Overview
This project develops an intelligent routing and energy management system for electric vehicles (EVs) in Hanoi, Vietnam. By integrating real-time traffic data from the TomTom API with a Model Predictive Control (MPC) algorithm, the system optimizes routes based on both travel time and energy efficiency. The solution bridges the gap between high-level path planning in Python and low-level physical validation in MATLAB/Simulink.

## Key Features
* **Multi-Objective MPC Optimization**: Balances time and energy consumption using an adaptive cost function that prioritizes energy conservation as the State of Charge (SOC) decreases.
* **Three-Level Battery Protection**: Implements safety buffers (Normal, Warning, Critical) to trigger proactive re-routing to the nearest V-Green charging station before battery depletion.
* **Real-time Traffic Integration**: Utilizes TomTom API to extract traffic flow density, enabling accurate energy consumption prediction during peak hours.
* **MATLAB/Simulink Co-simulation**: Exports 1-second resolution Drive Cycles to verify physical feasibility through high-fidelity vehicle dynamics and Thevenin battery models.
* **Digital Twin Dashboard**: A Streamlit-based web interface for real-time monitoring, route selection, and data visualization.

## Technology Stack
* **Core Logic**: Python 3.12, NetworkX, NumPy, SciPy.
* **Physical Simulation**: MATLAB R2024 / Simulink.
* **External APIs**: TomTom Routing & Traffic API, OpenTopoData.
* **Visualization**: Streamlit, Folium, Matplotlib.

## Getting Started

### 1. Installation
Clone the repository:
```bash
git clone [https://github.com/logan-124/EV-Routing-MPC-Hanoi.git](https://github.com/logan-124/EV-Routing-MPC-Hanoi.git)
cd EV-Routing-MPC-Hanoi
