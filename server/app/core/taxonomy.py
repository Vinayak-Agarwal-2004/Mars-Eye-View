# Taxonomy Mappings for Suffering Tracker
# Maps GDELT/ACLED codes to 5 Core Categories

COLORS = {
    "CONFLICT": "#ef4444",      # Red-500
    "VIOLENCE": "#f97316",      # Orange-500
    "PROTEST": "#eab308",       # Yellow-500
    "DISPLACEMENT": "#a855f7",  # Purple-500
    "DISASTER": "#3b82f6",      # Blue-500
    "CRIME": "#db2777",         # Pink-600 (New: Kidnapping, Drugs, Trafficking)
    "ACCIDENT": "#14b8a6",      # Teal-500 (New: Accidents)
    "OTHER": "#71717a"          # Zinc-500
}

# GDELT Event Codes (CAMEO)
# https://www.gdeltproject.org/data/lookups/CAMEO.eventcodes.txt
GDELT_MAPPING = {
    # Material Conflict (Red)
    "19": "CONFLICT",   # Fight
    "190": "CONFLICT",  # Use conventional military force
    "193": "CONFLICT",  # Fight with small arms and light weapons
    "194": "CONFLICT",  # Fight with artillery and tanks
    "20": "CONFLICT",   # Use unconventional mass violence
    
    # Violence vs Civilians / Assault (Orange)
    "18": "VIOLENCE",   # Assault
    "180": "VIOLENCE",  # Use unconventional violence
    "181": "CRIME",     # Abduct/hijack/take hostage (Moved to CRIME)
    "182.1": "CRIME",   # Sexually assault (Moved to CRIME/VIOLENCE)
    "145": "VIOLENCE",  # Violent protest (often riots)
    "173": "CRIME",     # Arrest, detain
    "174": "CRIME",     # Expel or deport

    # Protests (Yellow)
    "14": "PROTEST",    # Protest
    "141": "PROTEST",   # Demonstrate or rally
    "1411": "PROTEST",  # Demonstrate for leadership change
    
    # Displacement (Purple)
    "016": "DISPLACEMENT", # Grant asylum
    
    # Disaster (Blue) - Usually Theme-based
}

# Keywords for Theme-based classification (GDELT GKG)
THEME_MAPPING = {
    # Disaster
    "NATURAL_DISASTER": "DISASTER",
    "ENV_EARTHQUAKE": "DISASTER",
    "ENV_FLOOD": "DISASTER",
    "ENV_VOLCANO": "DISASTER",

    # Displacement
    "REFUGEES": "DISPLACEMENT",
    "DISPLACED": "DISPLACEMENT",
    
    # War/Conflict
    "ARMEDCONFLICT": "CONFLICT",
    "MILITARY": "CONFLICT",
    "CIVIL_WAR": "CONFLICT",

    # Violence/Terror
    "TERROR": "VIOLENCE",
    "SUICIDE_ATTACK": "VIOLENCE",
    "ASSASSINATION": "VIOLENCE",
    
    # Crime (New)
    "TAX_FNCACT_KIDNAPPING": "CRIME",
    "KIDNAP": "CRIME",
    "HOSTAGE": "CRIME",
    "HUMAN_TRAFFICKING": "CRIME",
    "WB_2433_HUMAN_TRAFFICKING": "CRIME",
    "DRUG_TRADE": "CRIME",
    "NARCOTICS": "CRIME",
    "ORGANIZED_CRIME": "CRIME",
    "TAX_DISEASE_DRUG_TRADE": "CRIME",
    "ARREST": "CRIME",
    "WB_2432_SEXUAL_VIOLENCE": "CRIME", # Often a war crime or civil crime
    "PIRACY": "CRIME",

    # Accident
    "ACCIDENT": "ACCIDENT",
    "TRANSPORT_ACCIDENT": "ACCIDENT",
    "MANMADE_DISASTER": "ACCIDENT"
}
