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
    # Material Conflict (Red) - Armed conflict and military actions
    "19": "CONFLICT",   # Fight
    "190": "CONFLICT",  # Use conventional military force
    "191": "CONFLICT",  # Impose blockade, restrict movement
    "192": "CONFLICT",  # Occupy territory
    "193": "CONFLICT",  # Fight with small arms and light weapons
    "194": "CONFLICT",  # Fight with artillery and tanks
    "195": "CONFLICT",  # Use WMD
    "196": "CONFLICT",  # Detonate nuclear weapons
    "20": "CONFLICT",   # Use unconventional mass violence
    "200": "CONFLICT",  # Mass violence
    "201": "CONFLICT",  # Engage in ethnic cleansing
    "202": "CONFLICT",  # Engage in mass killings
    "203": "CONFLICT",  # Engage in mass expulsion
    
    # Violence vs Civilians / Assault (Orange)
    "18": "VIOLENCE",   # Assault
    "180": "VIOLENCE",  # Use unconventional violence
    "181": "CRIME",     # Abduct/hijack/take hostage (Moved to CRIME)
    "182": "VIOLENCE",  # Physically assault
    "182.1": "CRIME",   # Sexually assault (Moved to CRIME/VIOLENCE)
    "183": "VIOLENCE",  # Conduct suicide, car, or other non-military bombing
    "145": "VIOLENCE",  # Violent protest (often riots)
    
    # Coercion/Crime (Pink)
    "17": "CRIME",      # Coerce
    "171": "CRIME",     # Seize or damage property
    "172": "CRIME",     # Impose administrative sanctions
    "173": "CRIME",     # Arrest, detain
    "174": "CRIME",     # Expel or deport
    "175": "CRIME",     # Use tactics of violent repression

    # Protests (Yellow)
    "14": "PROTEST",    # Protest
    "140": "PROTEST",   # Engage in political dissent
    "141": "PROTEST",   # Demonstrate or rally
    "1411": "PROTEST",  # Demonstrate for leadership change
    "142": "PROTEST",   # Conduct hunger strike
    "143": "PROTEST",   # Conduct strike or boycott
    "144": "PROTEST",   # Obstruct passage
    
    # Displacement (Purple)
    "016": "DISPLACEMENT", # Grant asylum
    "013": "DISPLACEMENT", # Provide aid (humanitarian)
    "0231": "DISPLACEMENT", # Appeal for humanitarian aid
    
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
