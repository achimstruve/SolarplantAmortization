import pvlib
import pandas as pd
import matplotlib.pyplot as plt

# Standort Brunsbüttel (Norddeutschland)
latitude = 54.17
longitude = 9.38
year = 2023
system_loss_percent = 15
max_feed_kw = 0.8
electricity_price = 0.36

# Verschiedene Anlagengrößen und Batteriekapazitäten definieren
scenarios = {
    '1.0 kWp': {'peak_power': 1.0, 'linestyle': '--'},
    '2.0 kWp': {'peak_power': 2.0, 'linestyle': '-'},
    '4.0 kWp': {'peak_power': 4.0, 'linestyle': ':'}
}

battery_scenarios = {
    '2.048 kWh': 2.048,
    '4.096 kWh': 4.096
}

def get_system_data(peak_power_kwp):
    """Daten für ein System mit gegebener Peakleistung abrufen"""
    data, _ = pvlib.iotools.get_pvgis_hourly(
        latitude=latitude, longitude=longitude,
        start=year, end=year,
        raddatabase='PVGIS-SARAH3',
        pvcalculation=True,
        peakpower=peak_power_kwp,
        loss=system_loss_percent,
        surface_tilt=35,
        surface_azimuth=180,
        outputformat='json'
    )
    return data

def simulate_system(data, battery_capacity_kwh, max_feed_kw):
    """Simuliert ein System mit gegebenen Parametern"""
    # Leistungsdaten extrahieren
    df = data.copy()
    df.index = pd.to_datetime(df.index)
    df['P'] = df['P'] / 1000  # in kW
    
    # Speicher-Simulation
    soc = 0.0  # Batterie zu Tagesbeginn leer
    buffered_feed = []
    limited_feed = []
    
    for pv in df['P']:
        # Mit 800W Limit ohne Speicher
        limited_feed.append(min(pv, max_feed_kw))
        
        # Mit Speicher
        if pv >= max_feed_kw:
            feed = max_feed_kw
            surplus = pv - feed
            soc = min(soc + surplus, battery_capacity_kwh)
        else:
            needed = max_feed_kw - pv
            discharge = min(needed, soc)
            feed = pv + discharge
            soc -= discharge
        soc = max(0, min(soc, battery_capacity_kwh))
        buffered_feed.append(feed)
    
    df['unlimited'] = df['P']
    df['limited'] = limited_feed
    df['buffered'] = buffered_feed
    
    # Kumulative Berechnung
    df['unlimited_cum'] = df['unlimited'].cumsum()
    df['limited_cum'] = df['limited'].cumsum()
    df['buffered_cum'] = df['buffered'].cumsum()
    
    return df

# Daten für alle Szenarien abrufen und simulieren
results = {}
linestyles = {}

for scenario_name, scenario_config in scenarios.items():
    print(f"Verarbeite {scenario_name}...")
    data = get_system_data(scenario_config['peak_power'])
    results[scenario_name] = {}
    
    for battery_name, battery_capacity in battery_scenarios.items():
        print(f"  - mit {battery_name} Batterie")
        results[scenario_name][battery_name] = simulate_system(data, battery_capacity, max_feed_kw)
    
    linestyles[scenario_name] = scenario_config['linestyle']

# Monatsweise Aggregation für alle Szenarien
monthly_data = {}
monthly_cum_data = {}

for scenario_name, battery_results in results.items():
    monthly_data[scenario_name] = {}
    monthly_cum_data[scenario_name] = {}
    
    for battery_name, df in battery_results.items():
        monthly_data[scenario_name][battery_name] = df.resample("ME").sum()
        monthly_cum_data[scenario_name][battery_name] = df.resample("ME").last()[['unlimited_cum', 'limited_cum', 'buffered_cum']]

# Preise für verschiedene Konfigurationen (in €)
prices = {
    '1.0 kWp': {'no_storage': 500, 'storage_2kwh': 1100, 'storage_4kwh': 1700},
    '2.0 kWp': {'no_storage': 700, 'storage_2kwh': 1390, 'storage_4kwh': 1990},
    '4.0 kWp': {'no_storage': 1100, 'storage_2kwh': 1970, 'storage_4kwh': 2570}  # Extrapoliert
}

# Plot mit 4x3 Subplots für Haupt-Szenarien + Amortisation + Jährliche Ersparnisse
fig, ((ax1, ax2, ax3), (ax4, ax5, ax6), (ax7, ax8, ax9), (ax10, ax11, ax12)) = plt.subplots(4, 3, figsize=(20, 20))

# Farben für die PV-Systeme
colors = ['C0', 'C1', 'C2']

# ===== SPALTE 1: OHNE SPEICHER =====
# Subplot 1: Monatliche Erträge ohne Speicher (nur 800W Limit)
scenario_type_no_storage = 'limited'
scenario_label_no_storage = '800W Limit'
color_no_storage = 'C1'

for scenario_name, battery_data in monthly_data.items():
    linestyle = linestyles[scenario_name]
    monthly = battery_data['2.048 kWh']  # Batterie ist irrelevant für diese Szenarien
    ax1.plot(monthly.index, monthly[scenario_type_no_storage], 
            label=f"{scenario_name} - {scenario_label_no_storage}", 
            linewidth=2, linestyle=linestyle, color=color_no_storage)

ax1.set_title("Monatliche Erträge - Ohne Speicher")
ax1.set_ylabel("Energieertrag (kWh/Monat)")
ax1.grid(True)
ax1.legend(fontsize=8)

# Subplot 4: Kumulative Erträge ohne Speicher (nur 800W Limit)
for scenario_name, battery_data in monthly_cum_data.items():
    linestyle = linestyles[scenario_name]
    monthly_cum = battery_data['2.048 kWh']
    ax4.plot(monthly_cum.index, monthly_cum[f'{scenario_type_no_storage}_cum'], 
            label=f"{scenario_name} - {scenario_label_no_storage}", 
            linewidth=2, linestyle=linestyle, color=color_no_storage)

ax4.set_title("Kumulative Erträge - Ohne Speicher")
ax4.set_ylabel("Kumulativer Energieertrag (kWh)")
ax4.set_xlabel("Monat")
ax4.grid(True)
ax4.legend(fontsize=8)

# ===== SPALTE 2: 2.048 kWh SPEICHER =====
# Subplot 2: Monatliche Erträge mit 2.048 kWh Batterie (nur Speicher-Szenario)
scenario_type_storage = 'buffered'
scenario_label_storage = '800W + Speicher'
color_storage = 'C2'

for scenario_name, battery_data in monthly_data.items():
    linestyle = linestyles[scenario_name]
    monthly = battery_data['2.048 kWh']
    ax2.plot(monthly.index, monthly[scenario_type_storage], 
            label=f"{scenario_name} - {scenario_label_storage}", 
            linewidth=2, linestyle=linestyle, color=color_storage)

ax2.set_title("Monatliche Erträge - 2.048 kWh Speicher")
ax2.set_ylabel("Energieertrag (kWh/Monat)")
ax2.grid(True)
ax2.legend(fontsize=8)

# Subplot 5: Kumulative Erträge mit 2.048 kWh Batterie (nur Speicher-Szenario)
for scenario_name, battery_data in monthly_cum_data.items():
    linestyle = linestyles[scenario_name]
    monthly_cum = battery_data['2.048 kWh']
    ax5.plot(monthly_cum.index, monthly_cum[f'{scenario_type_storage}_cum'], 
            label=f"{scenario_name} - {scenario_label_storage}", 
            linewidth=2, linestyle=linestyle, color=color_storage)

ax5.set_title("Kumulative Erträge - 2.048 kWh Speicher")
ax5.set_ylabel("Kumulativer Energieertrag (kWh)")
ax5.set_xlabel("Monat")
ax5.grid(True)
ax5.legend(fontsize=8)

# ===== SPALTE 3: 4.096 kWh SPEICHER =====
# Subplot 3: Monatliche Erträge mit 4.096 kWh Batterie (nur Speicher-Szenario)
for scenario_name, battery_data in monthly_data.items():
    linestyle = linestyles[scenario_name]
    monthly = battery_data['4.096 kWh']
    ax3.plot(monthly.index, monthly[scenario_type_storage], 
            label=f"{scenario_name} - {scenario_label_storage}", 
            linewidth=2, linestyle=linestyle, color=color_storage)

ax3.set_title("Monatliche Erträge - 4.096 kWh Speicher")
ax3.set_ylabel("Energieertrag (kWh/Monat)")
ax3.grid(True)
ax3.legend(fontsize=8)

# Subplot 6: Kumulative Erträge mit 4.096 kWh Batterie (nur Speicher-Szenario)
for scenario_name, battery_data in monthly_cum_data.items():
    linestyle = linestyles[scenario_name]
    monthly_cum = battery_data['4.096 kWh']
    ax6.plot(monthly_cum.index, monthly_cum[f'{scenario_type_storage}_cum'], 
            label=f"{scenario_name} - {scenario_label_storage}", 
            linewidth=2, linestyle=linestyle, color=color_storage)

ax6.set_title("Kumulative Erträge - 4.096 kWh Speicher")
ax6.set_ylabel("Kumulativer Energieertrag (kWh)")
ax6.set_xlabel("Monat")
ax6.grid(True)
ax6.legend(fontsize=8)

# ===== ANNOTATIONS =====
# Annotations für ohne Speicher (ax4)
annotation_color_no_storage = 'orange'
annotation_offset_no_storage = 0
x_offsets = [10, -60, -110]

for j, (scenario_name, battery_data) in enumerate(monthly_cum_data.items()):
    monthly_cum = battery_data['2.048 kWh']
    final_value = monthly_cum[f'{scenario_type_no_storage}_cum'].iloc[-1]
    
    ax4.annotate(f'{final_value:.1f} kWh', 
                 xy=(monthly_cum.index[-1], final_value),
                 xytext=(x_offsets[j], annotation_offset_no_storage), 
                 textcoords='offset points',
                 bbox=dict(boxstyle='round,pad=0.3', 
                          facecolor=annotation_color_no_storage, 
                          alpha=0.7 - j*0.1),
                 fontsize=7, fontweight='bold')

# Annotations für 2.048 kWh Speicher (ax5)
annotation_color_storage = 'lightgreen'
annotation_offset_storage = 0

for j, (scenario_name, battery_data) in enumerate(monthly_cum_data.items()):
    monthly_cum = battery_data['2.048 kWh']
    final_value = monthly_cum[f'{scenario_type_storage}_cum'].iloc[-1]
    
    ax5.annotate(f'{final_value:.1f} kWh', 
                 xy=(monthly_cum.index[-1], final_value),
                 xytext=(x_offsets[j], annotation_offset_storage), 
                 textcoords='offset points',
                 bbox=dict(boxstyle='round,pad=0.3', 
                          facecolor=annotation_color_storage, 
                          alpha=0.7 - j*0.1),
                 fontsize=7, fontweight='bold')

# Annotations für 4.096 kWh Speicher (ax6)
for j, (scenario_name, battery_data) in enumerate(monthly_cum_data.items()):
    monthly_cum = battery_data['4.096 kWh']
    final_value = monthly_cum[f'{scenario_type_storage}_cum'].iloc[-1]
    
    ax6.annotate(f'{final_value:.1f} kWh', 
                 xy=(monthly_cum.index[-1], final_value),
                 xytext=(x_offsets[j], annotation_offset_storage), 
                 textcoords='offset points',
                 bbox=dict(boxstyle='round,pad=0.3', 
                          facecolor=annotation_color_storage, 
                          alpha=0.7 - j*0.1),
                 fontsize=7, fontweight='bold')

# ===== AMORTISATIONSBERECHNUNG =====
# Sammle Daten für Amortisationsberechnung
amortization_data = {}

for scenario_name, battery_results in results.items():
    amortization_data[scenario_name] = {}
    
    # Ohne Speicher (800W Limit)
    annual_yield_no_storage = battery_results['2.048 kWh']['limited'].sum()
    annual_savings_no_storage = annual_yield_no_storage * electricity_price
    investment_no_storage = prices[scenario_name]['no_storage']
    amortization_no_storage = investment_no_storage / annual_savings_no_storage if annual_savings_no_storage > 0 else float('inf')
    
    # Mit 2.048 kWh Speicher
    annual_yield_2kwh = battery_results['2.048 kWh']['buffered'].sum()
    annual_savings_2kwh = annual_yield_2kwh * electricity_price
    investment_2kwh = prices[scenario_name]['storage_2kwh']
    amortization_2kwh = investment_2kwh / annual_savings_2kwh if annual_savings_2kwh > 0 else float('inf')
    
    # Mit 4.096 kWh Speicher
    annual_yield_4kwh = battery_results['4.096 kWh']['buffered'].sum()
    annual_savings_4kwh = annual_yield_4kwh * electricity_price
    investment_4kwh = prices[scenario_name]['storage_4kwh']
    amortization_4kwh = investment_4kwh / annual_savings_4kwh if annual_savings_4kwh > 0 else float('inf')
    
    amortization_data[scenario_name] = {
        'no_storage': {'years': amortization_no_storage, 'investment': investment_no_storage, 'savings': annual_savings_no_storage},
        'storage_2kwh': {'years': amortization_2kwh, 'investment': investment_2kwh, 'savings': annual_savings_2kwh},
        'storage_4kwh': {'years': amortization_4kwh, 'investment': investment_4kwh, 'savings': annual_savings_4kwh}
    }

# Subplot 7: Amortisation ohne Speicher
scenario_names = list(amortization_data.keys())
amortization_years_no_storage = [amortization_data[name]['no_storage']['years'] for name in scenario_names]
investments_no_storage = [amortization_data[name]['no_storage']['investment'] for name in scenario_names]

bars7 = ax7.bar(scenario_names, amortization_years_no_storage, color='orange', alpha=0.7)
ax7.set_title("Amortisationszeit - Ohne Speicher")
ax7.set_ylabel("Jahre")
ax7.set_ylim(0, max(amortization_years_no_storage) * 1.1)
ax7.grid(True, alpha=0.3)

# Annotationen mit Investitionskosten
for i, (bar, investment) in enumerate(zip(bars7, investments_no_storage)):
    height = bar.get_height()
    ax7.annotate(f'{height:.1f} Jahre\n({investment}€)', 
                xy=(bar.get_x() + bar.get_width()/2, height),
                xytext=(0, 3), textcoords='offset points',
                ha='center', va='bottom', fontsize=8, fontweight='bold')

# Subplot 8: Amortisation mit 2.048 kWh Speicher
amortization_years_2kwh = [amortization_data[name]['storage_2kwh']['years'] for name in scenario_names]
investments_2kwh = [amortization_data[name]['storage_2kwh']['investment'] for name in scenario_names]

bars8 = ax8.bar(scenario_names, amortization_years_2kwh, color='lightgreen', alpha=0.7)
ax8.set_title("Amortisationszeit - 2.048 kWh Speicher")
ax8.set_ylabel("Jahre")
ax8.set_ylim(0, max(amortization_years_2kwh) * 1.1)
ax8.grid(True, alpha=0.3)

# Annotationen mit Investitionskosten
for i, (bar, investment) in enumerate(zip(bars8, investments_2kwh)):
    height = bar.get_height()
    ax8.annotate(f'{height:.1f} Jahre\n({investment}€)', 
                xy=(bar.get_x() + bar.get_width()/2, height),
                xytext=(0, 3), textcoords='offset points',
                ha='center', va='bottom', fontsize=8, fontweight='bold')

# Subplot 9: Amortisation mit 4.096 kWh Speicher
amortization_years_4kwh = [amortization_data[name]['storage_4kwh']['years'] for name in scenario_names]
investments_4kwh = [amortization_data[name]['storage_4kwh']['investment'] for name in scenario_names]

bars9 = ax9.bar(scenario_names, amortization_years_4kwh, color='darkgreen', alpha=0.7)
ax9.set_title("Amortisationszeit - 4.096 kWh Speicher")
ax9.set_ylabel("Jahre")
ax9.set_ylim(0, max(amortization_years_4kwh) * 1.1)
ax9.grid(True, alpha=0.3)

# Annotationen mit Investitionskosten
for i, (bar, investment) in enumerate(zip(bars9, investments_4kwh)):
    height = bar.get_height()
    ax9.annotate(f'{height:.1f} Jahre\n({investment}€)', 
                xy=(bar.get_x() + bar.get_width()/2, height),
                xytext=(0, 3), textcoords='offset points',
                ha='center', va='bottom', fontsize=8, fontweight='bold')

# ===== JÄHRLICHE ERSPARNISSE =====
# Subplot 10: Jährliche Ersparnisse ohne Speicher
annual_savings_no_storage = [amortization_data[name]['no_storage']['savings'] for name in scenario_names]

bars10 = ax10.bar(scenario_names, annual_savings_no_storage, color='orange', alpha=0.7)
ax10.set_title("Jährliche Ersparnisse - Ohne Speicher")
ax10.set_ylabel("Ersparnisse (€/Jahr)")
ax10.set_ylim(0, max(annual_savings_no_storage) * 1.1)
ax10.grid(True, alpha=0.3)

# Annotationen mit jährlichen Ersparnissen
for i, bar in enumerate(bars10):
    height = bar.get_height()
    yield_kwh = annual_savings_no_storage[i] / electricity_price
    ax10.annotate(f'{height:.0f}€/Jahr\n({yield_kwh:.0f} kWh)', 
                 xy=(bar.get_x() + bar.get_width()/2, height),
                 xytext=(0, 3), textcoords='offset points',
                 ha='center', va='bottom', fontsize=8, fontweight='bold')

# Subplot 11: Jährliche Ersparnisse mit 2.048 kWh Speicher
annual_savings_2kwh = [amortization_data[name]['storage_2kwh']['savings'] for name in scenario_names]

bars11 = ax11.bar(scenario_names, annual_savings_2kwh, color='lightgreen', alpha=0.7)
ax11.set_title("Jährliche Ersparnisse - 2.048 kWh Speicher")
ax11.set_ylabel("Ersparnisse (€/Jahr)")
ax11.set_ylim(0, max(annual_savings_2kwh) * 1.1)
ax11.grid(True, alpha=0.3)

# Annotationen mit jährlichen Ersparnissen
for i, bar in enumerate(bars11):
    height = bar.get_height()
    yield_kwh = annual_savings_2kwh[i] / electricity_price
    ax11.annotate(f'{height:.0f}€/Jahr\n({yield_kwh:.0f} kWh)', 
                 xy=(bar.get_x() + bar.get_width()/2, height),
                 xytext=(0, 3), textcoords='offset points',
                 ha='center', va='bottom', fontsize=8, fontweight='bold')

# Subplot 12: Jährliche Ersparnisse mit 4.096 kWh Speicher
annual_savings_4kwh = [amortization_data[name]['storage_4kwh']['savings'] for name in scenario_names]

bars12 = ax12.bar(scenario_names, annual_savings_4kwh, color='darkgreen', alpha=0.7)
ax12.set_title("Jährliche Ersparnisse - 4.096 kWh Speicher")
ax12.set_ylabel("Ersparnisse (€/Jahr)")
ax12.set_ylim(0, max(annual_savings_4kwh) * 1.1)
ax12.grid(True, alpha=0.3)

# Annotationen mit jährlichen Ersparnissen
for i, bar in enumerate(bars12):
    height = bar.get_height()
    yield_kwh = annual_savings_4kwh[i] / electricity_price
    ax12.annotate(f'{height:.0f}€/Jahr\n({yield_kwh:.0f} kWh)', 
                 xy=(bar.get_x() + bar.get_width()/2, height),
                 xytext=(0, 3), textcoords='offset points',
                 ha='center', va='bottom', fontsize=8, fontweight='bold')

plt.tight_layout()

# Plot speichern
plt.savefig('balkonkraftwerk_analysis.png', dpi=300, bbox_inches='tight')
print("Plot gespeichert als 'balkonkraftwerk_analysis.png'")

plt.show()

# Jahreserträge und Amortisation anzeigen
for scenario_name, battery_results in results.items():
    print(f"\n=== {scenario_name} System ===")
    
    for battery_name, df in battery_results.items():
        total_unlimited = df['unlimited'].sum()
        total_limited = df['limited'].sum()
        total_buffered = df['buffered'].sum()
        
        print(f"\n--- {battery_name} Batterie ---")
        print("Jahresertrag ohne Limit:       ", round(total_unlimited, 2), "kWh")
        print("Jahresertrag mit 800W Limit:   ", round(total_limited, 2), "kWh")
        print("Jahresertrag mit 800W + Akku:  ", round(total_buffered, 2), "kWh")
        print("Puffer-Mehrertrag:             ", round(total_buffered - total_limited, 2), "kWh")
        
        # Zusätzliche Batterie-Effizienz Analyse
        if battery_name == '4.096 kWh':
            # Vergleich mit 2.048 kWh Batterie
            df_small = battery_results['2.048 kWh']
            total_buffered_small = df_small['buffered'].sum()
            additional_yield = total_buffered - total_buffered_small
            print(f"Zusätzlicher Ertrag vs 2.048 kWh: {round(additional_yield, 2)} kWh")
            print(f"Effizienz-Steigerung:           {round(additional_yield/total_buffered_small*100, 1)}%")

# Amortisationsanalyse in der Konsole
print(f"\n{'='*60}")
print("AMORTISATIONSANALYSE")
print(f"Strompreis: {electricity_price:.2f} €/kWh")
print(f"{'='*60}")

for scenario_name in amortization_data.keys():
    print(f"\n=== {scenario_name} System ===")
    
    # Ohne Speicher
    data_no_storage = amortization_data[scenario_name]['no_storage']
    print(f"Ohne Speicher:")
    print(f"  Investition: {data_no_storage['investment']}€")
    print(f"  Jährliche Ersparnis: {data_no_storage['savings']:.2f}€")
    print(f"  Amortisationszeit: {data_no_storage['years']:.1f} Jahre")
    
    # Mit 2.048 kWh Speicher
    data_2kwh = amortization_data[scenario_name]['storage_2kwh']
    print(f"Mit 2.048 kWh Speicher:")
    print(f"  Investition: {data_2kwh['investment']}€")
    print(f"  Jährliche Ersparnis: {data_2kwh['savings']:.2f}€")
    print(f"  Amortisationszeit: {data_2kwh['years']:.1f} Jahre")
    
    # Mit 4.096 kWh Speicher
    data_4kwh = amortization_data[scenario_name]['storage_4kwh']
    print(f"Mit 4.096 kWh Speicher:")
    print(f"  Investition: {data_4kwh['investment']}€")
    print(f"  Jährliche Ersparnis: {data_4kwh['savings']:.2f}€")
    print(f"  Amortisationszeit: {data_4kwh['years']:.1f} Jahre")
    
    # Vergleichsanalyse
    best_option = min([
        ('Ohne Speicher', data_no_storage['years']),
        ('2.048 kWh Speicher', data_2kwh['years']),
        ('4.096 kWh Speicher', data_4kwh['years'])
    ], key=lambda x: x[1])
    
    print(f"  → Beste Option: {best_option[0]} ({best_option[1]:.1f} Jahre)")

print(f"\n{'='*60}")
print("EXTRAPOLIERTE PREISE für 4.0 kWp:")
print("Ohne Speicher: 1100€ | Mit 2 kWh: 1970€ | Mit 4 kWh: 2570€")
print(f"{'='*60}")
