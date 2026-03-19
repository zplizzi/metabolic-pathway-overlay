"""
Maps pathway diagram node labels to test data from test_data CSVs.

Returns a dict keyed by normalized node label, each containing all matching
datasets with full history. The viewer fetches this once and uses it to
render overlays and detail panels.

MAPPING RULES:
  - Only exact analyte matches. No inferred/indirect relationships.
  - If a test measures "Riboflavin", it maps to "Riboflavin", NOT to FMN or FAD.
  - OAT measures urine organic acids (free acid forms, not CoA esters).
  - Theriome measures whole blood metabolites directly.

VIBRANT NUTRIENT ZOOMER — exact forms measured (from Nutrient-Zoomer-Markers-List.pdf):
  Vitamins:
    B1  = Thiamine                      (Serum + WBC)
    B2  = Riboflavin                    (Serum + WBC)
    B3  = Niacin (nicotinic acid)       (Serum + WBC)
    B5  = Pantothenic Acid              (Serum + WBC)
    B6  = Pyridoxal 5'-Phosphate (P5P)  (Serum + WBC)
    B9  = Folate                        (Serum + RBC)
    B12 = Cobalamin                     (Serum + WBC)
    MMA = Methylmalonic acid            (Serum only)
    A   = Retinol                       (Serum + WBC)
    D3  = Cholecalciferol               (Serum + WBC)
    D   = 25-Hydroxy Vitamin D          (Serum only)
    E   = Alpha Tocopherol              (Serum + WBC)
    K1  = Phylloquinone                 (Serum + WBC)
    K2  = Menaquinone-4                 (Serum + WBC)
    C   = Ascorbic Acid                 (Serum + WBC)
    CoQ10 = Coenzyme Q10                (Serum + WBC)
    Myo-Inositol                        (Serum + WBC)
    Choline                             (Serum + WBC)
  Minerals:
    Calcium, Chromium, Copper, Iron (Serum+RBC), Magnesium (Serum+RBC),
    Manganese, Potassium, Selenium, Sodium, Zinc
  Amino Acids:
    Arginine (Serum), Asparagine (Serum+WBC), Carnitine (Serum+WBC),
    Citrulline (Serum), Cysteine (Serum+WBC), Glutamine (Serum+WBC),
    Glutathione (WBC), Isoleucine (Serum), Leucine (Serum),
    Serine (Serum+WBC), Valine (Serum)
  Fatty Acids (all RBC):
    AA, LA, EPA, DPA, DHA, Omega-3 Index, Total Omega-3, Total Omega-6
"""

import csv
import math
import re
from pathlib import Path


# ── Mapping table ────────────────────────────────────────────────────────────
# Maps normalized diagram node label → list of (csv_source, analyte_key, note)
# csv_source is one of: "theriome", "oat", "vibrant", "cma"
# analyte_key is the exact name/key used in that CSV
# note (optional) provides context — but ALL mappings are exact matches

LABEL_TO_ANALYTES = {
    # ── Amino Acids ──────────────────────────────────────────────────────────
    "Alanine":       [("theriome", "L-Alanine", None)],
    "Arginine":      [("theriome", "L-Arginine", None), ("vibrant", "Arginine", None), ("cma", "Arginine", None)],
    "Asparagine":    [("theriome", "L-Asparagine", None), ("vibrant", "Asparagine", None), ("cma", "Asparagine", None)],
    "Aspartate":     [("theriome", "L-Aspartic acid", None)],
    "Cysteine":      [("theriome", "L-Cysteine", None), ("vibrant", "Cysteine", None), ("cma", "Cysteine", None)],
    "Cystine":       [("theriome", "L-Cystine", None)],
    "Glutamate":     [("theriome", "L-Glutamic acid", None)],
    "Glutamine":     [("theriome", "L-Glutamine", None), ("vibrant", "Glutamine", None), ("cma", "L-Glutamine", None)],
    "Glycine":       [("theriome", "Glycine", None), ("cma", "Glycine", None)],
    "Histidine":     [("theriome", "L-Histidine", None), ("cma", "Histidine", None)],
    "Isoleucine":    [("theriome", "L-Isoleucine", None), ("vibrant", "Isoleucine", None), ("cma", "Isoleucine", None)],
    "Leucine":       [("theriome", "L-Leucine", None), ("vibrant", "Leucine", None), ("cma", "Leucine", None)],
    "Methionine":    [("theriome", "L-Methionine", None), ("cma", "Methionine", None)],
    "Phenylalanine": [("theriome", "L-Phenylalanine", None), ("cma", "Phenylalanine", None)],
    "Proline":       [("theriome", "L-Proline", None)],
    "Serine":        [("theriome", "L-Serine", None), ("vibrant", "Serine", None), ("cma", "L-Serine", None)],
    "Threonine":     [("theriome", "L-Threonine", None), ("cma", "Threonine", None)],
    "Tryptophan":    [("theriome", "L-Tryptophan", None), ("cma", "Tryptophan", None)],
    "Tyrosine":      [("theriome", "L-Tyrosine", None), ("cma", "L-Tyrosine", None)],
    "Valine":        [("theriome", "L-Valine", None), ("vibrant", "Valine", None), ("cma", "Valine", None)],

    # ── Urea Cycle ───────────────────────────────────────────────────────────
    "Ornithine":     [("theriome", "Ornithine", None)],
    "Citrulline":    [("vibrant", "Citrulline", None)],

    # ── Krebs Cycle ──────────────────────────────────────────────────────────
    "Citrate":       [("theriome", "Citric acid", None), ("oat", "Citric", None)],
    "D-Isocitrate":  [("theriome", "Isocitric acid", None)],
    "Isocitrate":    [("theriome", "Isocitric acid", None)],
    "cis-Aconitate": [("theriome", "cis-Aconitic acid", None), ("oat", "Aconitic", None)],
    "α-Ketoglutarate": [("theriome", "Oxoglutaric acid", None), ("oat", "2-Oxoglutaric", None)],
    "α-KG":          [("theriome", "Oxoglutaric acid", None), ("oat", "2-Oxoglutaric", None)],
    "Succinate":     [("theriome", "Succinic Acid", None), ("oat", "Succinic", None)],
    "Fumarate":      [("theriome", "Fumaric acid", None), ("oat", "Fumaric", None)],
    "Malate":        [("theriome", "Malic acid", None), ("oat", "Malic", None)],

    # ── Glycolysis / Gluconeogenesis ─────────────────────────────────────────
    "Lactate":       [("oat", "Lactic", None)],
    "Pyruvate":      [("oat", "Pyruvic", None)],

    # ── Organic Acids ────────────────────────────────────────────────────────
    "Oxalate":       [("theriome", "Oxalic acid", None), ("oat", "Oxalic", None)],
    "Glycolate":     [("theriome", "Glycolic acid", None), ("oat", "Glycolic", None)],
    "Methylmalonate": [("theriome", "Methylmalonic acid", None), ("oat", "Methylmalonic", None),
                       ("vibrant", "MMA (Methylmalonic acid)", None), ("labcorp", "Methylmalonic acid (nmol/L)", None)],
    "Malonate":      [("theriome", "Malonic acid", None), ("oat", "Malonic", None)],

    # ── Neurotransmitters ────────────────────────────────────────────────────
    "Histamine":     [("theriome", "Histamine", None), ("labcorp", "Histamine, Plasma (ng/mL)", None)],
    "Serotonin":     [("theriome", "Serotonin", None), ("labcorp", "Serotonin, Serum (ng/mL)", None)],
    "5-HIAA":        [("oat", "5-Hydroxyindoleacetic (5-HIAA)", None)],
    "GABA":          [("theriome", "gamma-Aminobutyric acid", None)],
    "Tyramine":      [("theriome", "Tyramine", None)],
    "Tryptamine":    [("theriome", "Tryptamine", None)],
    "L-Dopa":        [("theriome", "L-Dopa", None)],

    # ── Neurotransmitter Metabolites ─────────────────────────────────────────
    "HVA":           [("oat", "Homovanillic (HVA)", None)],
    "VMA":           [("oat", "Vanillylmandelic (VMA)", None)],
    "DOPAC":         [("oat", "Dihydroxyphenylacetic (DOPAC)", None)],
    "Quinolinate":   [("theriome", "Quinolinic acid", None), ("oat", "Quinolinic", None)],
    "Quinolinic Acid": [("theriome", "Quinolinic acid", None), ("oat", "Quinolinic", None)],
    "Kynurenic Acid": [("oat", "Kynurenic", None)],
    "Kynurenate":    [("oat", "Kynurenic", None)],

    # ── B3 / NAD+ pathway ───────────────────────────────────────────────────
    # Vibrant B3 measures niacin (nicotinic acid) directly
    "Nicotinic Acid": [("theriome", "Nicotinic acid", None), ("vibrant", "Vitamin B3", "Vibrant measures niacin (nicotinic acid)"), ("cma", "Vitamin B3", None), ("labcorp", "Vitamin B3 (ng/mL)", None)],
    "Nicotinamide":  [("theriome", "Niacinamide", None)],
    # No direct NAD+ measurement available

    # ── B Vitamins / Cofactors ───────────────────────────────────────────────
    # Vibrant B6 = Pyridoxal 5'-Phosphate (P5P) specifically
    "P5P":           [("vibrant", "Vitamin B6", "Vibrant measures P5P (pyridoxal 5'-phosphate)"), ("cma", "Vitamin B6", None), ("labcorp", "Vitamin B6, plasma (ng/mL)", None)],
    # Pyridoxamine and pyridoxine are different B6 vitamers — Vibrant does NOT measure these
    "Pyridoxamine":  [("theriome", "Pyridoxamine", None)],
    "Pyridoxine":    [("theriome", "Pyridoxine", None)],
    # Vibrant B2 = Riboflavin directly
    "Riboflavin":    [("vibrant", "Vitamin B2", "Vibrant measures riboflavin directly"), ("cma", "Vitamin B2", None), ("labcorp", "Vitamin B2 (nmol/L)", None)],
    # Vibrant B1 = Thiamine directly
    "Thiamine":      [("vibrant", "Vitamin B1", "Vibrant measures thiamine directly"), ("cma", "Vitamin B1", None)],
    # Vibrant B12 = Cobalamin directly
    "Cobalamin":     [("vibrant", "Vitamin B12", "Vibrant measures cobalamin directly"), ("cma", "Vitamin B12", None), ("labcorp", "Vitamin B12 Level (pg/mL)", None)],
    # Vibrant B9 = Folate directly
    "Folate":        [("vibrant", "Folate (Vitamin B9)", "Vibrant measures folate (serum + RBC)"), ("cma", "Vitamin B9", None), ("labcorp", "Vitamin B9 (folate) (ng/mL)", None)],
    # Vibrant B5 = Pantothenic Acid; OAT also measures pantothenic acid directly
    "Pantothenate":  [("vibrant", "Vitamin B5", "Vibrant measures pantothenic acid"), ("oat", "Pantothenic (B5)", None), ("cma", "Pantothenic Acid", None), ("labcorp", "Vitamin B5 (ng/mL)", None)],
    # OAT pyridoxic acid is a direct measurement (B6 catabolite)
    "Pyridoxic Acid": [("oat", "Pyridoxic (B6)", None)],

    # ── Redox / Energy ───────────────────────────────────────────────────────
    # Vibrant measures CoQ10 directly — not the same as ubiquinone (Q) or ubiquinol (QH₂)
    "CoQ10":         [("vibrant", "Coenzyme Q10", "Vibrant measures CoQ10 directly (serum + WBC)"), ("cma", "Coenzyme Q10", None), ("labcorp", "CoQ 10 (ug/mL)", None)],
    "Glutathione":   [("theriome", "Glutathione", None), ("vibrant", "Glutathione", "Vibrant measures glutathione in WBC"), ("cma", "Glutathione", None)],
    "GSH":           [("theriome", "Glutathione", None), ("vibrant", "Glutathione", "Vibrant measures glutathione in WBC"), ("cma", "Glutathione", None)],
    "Pyroglutamate": [("theriome", "Pyroglutamic acid", None), ("oat", "Pyroglutamic", None)],
    "Ascorbate":     [("vibrant", "Vitamin C", "Vibrant measures ascorbic acid"), ("oat", "Ascorbic", None), ("cma", "Vitamin C", None), ("labcorp", "Vitamin C (mg/dL)", None)],
    "Vitamin C":     [("vibrant", "Vitamin C", "Vibrant measures ascorbic acid"), ("oat", "Ascorbic", None), ("cma", "Vitamin C", None), ("labcorp", "Vitamin C (mg/dL)", None)],

    # ── Other Metabolites ────────────────────────────────────────────────────
    "Taurine":       [("theriome", "Taurine", None), ("cma", "Taurine", None)],
    "Hypotaurine":   [("theriome", "Hypotaurine", None)],
    "Sarcosine":     [("theriome", "Sarcosine", None)],
    "Homocysteine":  [("labcorp", "Homocysteine (umol/L)", None)],
    "Cystathionine": [("theriome", "L-Cystathionine", None)],
    "Carnitine":     [("vibrant", "Carnitine", None), ("cma", "Carnitine", None)],
    "Choline":       [("vibrant", "Choline", None), ("cma", "Choline", None)],
    "Inositol":      [("vibrant", "Inositol", "Vibrant measures myo-inositol"), ("theriome", "myo-Inositol", None), ("cma", "Inositol", None)],
    "Uracil":        [("theriome", "Uracil", None), ("oat", "Uracil", None)],
    "Thymine":       [("theriome", "Thymine", None), ("oat", "Thymine", None)],
    "Uridine":       [("theriome", "Uridine", None)],
    "Adenosine":     [("theriome", "Adenosine", None)],
    "Ethanolamine":  [("theriome", "Ethanolamine", None)],
    "Putrescine":    [("theriome", "Putrescine", None)],
    "Spermidine":    [("theriome", "Spermidine", None)],
    "Spermine":      [("theriome", "Spermine", None)],
    "Mannitol":      [("theriome", "Mannitol", None)],
    "beta-Alanine":  [("theriome", "beta-Alanine", None)],
    "β-Alanine":     [("theriome", "beta-Alanine", None)],
    "4-Hydroxyproline": [("theriome", "4-Hydroxyproline", None)],
    "Hydroxyproline": [("theriome", "4-Hydroxyproline", None)],

    # ── Minerals (shown as cofactors in diagram) ────────────────────────────
    # Vibrant measures total element levels; ionic forms (Fe²⁺ etc.) map to same data
    "Fe":   [("vibrant", "Iron", None), ("cma", "Iron", None), ("labcorp", "iron (transferrin-bound) (ug/dL)", None)],
    "Fe²⁺": [("vibrant", "Iron", None), ("cma", "Iron", None), ("labcorp", "iron (transferrin-bound) (ug/dL)", None)],
    "Fe³⁺": [("vibrant", "Iron", None), ("cma", "Iron", None), ("labcorp", "iron (transferrin-bound) (ug/dL)", None)],
    "Cu":   [("vibrant", "Copper", None), ("cma", "Copper", None), ("labcorp", "Copper, Serum or Plasma (ug/L)", None)],
    "Cu²⁺": [("vibrant", "Copper", None), ("cma", "Copper", None), ("labcorp", "Copper, Serum or Plasma (ug/L)", None)],
    "Zn":   [("vibrant", "Zinc", None), ("cma", "Zinc", None), ("labcorp", "zinc, plasma (ug/dL)", None)],
    "Zn²⁺": [("vibrant", "Zinc", None), ("cma", "Zinc", None), ("labcorp", "zinc, plasma (ug/dL)", None)],
    "Mg":   [("vibrant", "Magnesium", None), ("cma", "Magnesium", None), ("labcorp", "magnesium, rbc (mg/dL)", None)],
    "Mg²⁺": [("vibrant", "Magnesium", None), ("cma", "Magnesium", None), ("labcorp", "magnesium, rbc (mg/dL)", None)],
    "Mn":   [("vibrant", "Manganese", None), ("cma", "Manganese", None), ("labcorp", "manganese, blood (ug/L)", None)],
    "Mn²⁺": [("vibrant", "Manganese", None), ("cma", "Manganese", None), ("labcorp", "manganese, blood (ug/L)", None)],
    "Se":   [("vibrant", "Selenium", None), ("cma", "Selenium", None), ("labcorp", "SELENIUM, blood (ug/L)", None)],
    "Ca":   [("vibrant", "Calcium", None), ("cma", "Calcium", None), ("labcorp", "Calcium Level (mg/dL)", None)],
    "Ca²⁺": [("vibrant", "Calcium", None), ("cma", "Calcium", None), ("labcorp", "Calcium Level (mg/dL)", None)],

    # ── Microbial markers ────────────────────────────────────────────────────
    "Hippurate":     [("oat", "Hippuric", None)],
    "HPHPA":         [("oat", "HPHPA", None)],
    "4-Cresol":      [("oat", "4-Cresol", None)],
    "Arabinose":     [("oat", "Arabinose", None)],

    # ── Fatty Acids ──────────────────────────────────────────────────────────
    "Linoleic acid":  [("theriome", "Linoleic acid", None), ("vibrant", "LA (Linoleic acid)", None)],
    "α-Linolenic acid": [("theriome", "alpha-Linolenic acid", None)],

    # ── Vitamins not on pathway diagram but tested across multiple sources ──
    "Vitamin A":     [("vibrant", "Vitamin A", None), ("cma", "Vitamin A", None),
                      ("labcorp", "vitamin A, serum (labcorp) (ug/dL)", None)],
    "Vitamin D":     [("vibrant", "Vitamin D 25-OH", None), ("cma", "Vitamin D", None),
                      ("labcorp", "Vitamin D 25 Hydroxy (ng/mL)", None)],
    "Vitamin E":     [("vibrant", "Vitamin E", None), ("labcorp", "Vitamin E, ALPHA TOCOPHEROL (mg/dL)", None),
                      ("cma", "Delta Tocotrienol", "Delta tocotrienol is a vitamin E form"),
                      ("theriome", "alpha-Tocopherol", None)],
    "Vitamin K1":    [("vibrant", "Vitamin K1", None), ("cma", "Vitamin K1", None)],
    "Vitamin K2":    [("vibrant", "Vitamin K2", None)],

    # ── Detox markers ────────────────────────────────────────────────────────
    "N-Acetylcysteine": [("oat", "N-Acetylcysteine (NAC)", None)],
    "NAC":           [("oat", "N-Acetylcysteine (NAC)", None)],
    "Orotic Acid":   [("oat", "Orotic", None)],
    "Orotate":       [("oat", "Orotic", None)],
}

# ── Alternate label forms ────────────────────────────────────────────────────
# Each canonical label in LABEL_TO_ANALYTES can have multiple aliases listed here.
# Format: canonical_key → [alias1, alias2, ...].
# Also supports "Full Name (ABBREV)" patterns — both the full name and the
# parenthesized abbreviation are auto-generated as aliases.

_ALIAS_GROUPS = {
    # Abbreviations and common name variants
    "Nicotinic Acid": ["NA", "Niacin", "Nicotinic Acid (NA)", "Vitamin B3", "Vitamin B3 (ng/mL)"],
    "Nicotinamide":   ["NAM", "Niacinamide", "Nicotinamide (NAM)"],
    "Quinolinate":    ["QA", "Quinolinic acid", "Quinolinic", "Quinolinate (QA)"],
    "Methylmalonate": ["Methylmalonic acid", "Methylmalonic", "MMA", "MMA (Methylmalonic acid)", "Methylmalonic acid (nmol/L)"],

    # Krebs cycle
    "α-Ketoglutarate": ["alpha-Ketoglutarate", "a-Ketoglutarate", "2-Oxoglutarate"],
    "α-KG":            ["a-KG"],
    "Succinate":       ["Succinate / Succinyl-CoA", "Succinic Acid", "Succinic"],
    "Citrate":         ["Citric acid", "Citric"],
    "D-Isocitrate":    ["Isocitric acid"],
    "Isocitrate":      ["Isocitric acid"],
    "cis-Aconitate":   ["cis-Aconitic acid", "Aconitic"],
    "Fumarate":        ["Fumaric acid", "Fumaric"],
    "Malate":          ["Malic acid", "Malic"],
    "Oxalate":         ["Oxalic acid", "Oxalic"],
    "Glycolate":       ["Glycolic acid", "Glycolic"],
    "Malonate":        ["Malonic acid", "Malonic"],
    "Lactate":         ["Lactic"],
    "Pyruvate":        ["Pyruvic"],
    "Pyroglutamate":   ["Pyroglutamic acid", "Pyroglutamic"],

    # B vitamins / cofactors
    "P5P":           ["Pyridoxal 5-Phosphate", "PLP", "Pyridoxal 5'-Phosphate", "Vitamin B6", "Vitamin B6, plasma (ng/mL)"],
    "CoQ10":         ["Coenzyme Q10", "Coenzyme Q₁₀", "CoQ 10 (ug/mL)"],
    "GSH":           ["Reduced Glutathione", "Glutathione (GSH)"],
    "Ascorbate":     ["Ascorbic acid", "Ascorbic", "Vitamin C", "Vitamin C (mg/dL)"],
    "Riboflavin":    ["Vitamin B2", "Vitamin B2 (nmol/L)"],
    "Thiamine":      ["Vitamin B1"],
    "Cobalamin":     ["Vitamin B12", "Vitamin B12 Level (pg/mL)"],
    "Folate":        ["Folate (Vitamin B9)", "Vitamin B9", "Vitamin B9 (folate) (ng/mL)"],
    "Pantothenate":  ["Pantothenic Acid", "Pantothenic (B5)", "Vitamin B5", "Vitamin B5 (ng/mL)"],
    "Hippurate":     ["Hippuric acid", "Hippuric"],
    "Orotate":       ["Orotic acid", "Orotic"],
    "N-Acetylcysteine": ["N-Acetylcysteine (NAC)"],
    "Kynurenic Acid": ["Kynurenic acid", "Kynurenic"],
    "Inositol":      ["myo-Inositol"],

    # Amino acids — CSV name variants
    "Arginine":      ["L-Arginine"],
    "Asparagine":    ["L-Asparagine"],
    "Aspartate":     ["L-Aspartic acid"],
    "Cysteine":      ["L-Cysteine"],
    "Cystine":       ["L-Cystine"],
    "Glutamate":     ["L-Glutamic acid"],
    "Glutamine":     ["L-Glutamine"],
    "Histidine":     ["L-Histidine"],
    "Isoleucine":    ["L-Isoleucine"],
    "Leucine":       ["L-Leucine"],
    "Methionine":    ["L-Methionine"],
    "Phenylalanine": ["L-Phenylalanine"],
    "Proline":       ["L-Proline"],
    "Serine":        ["L-Serine"],
    "Threonine":     ["L-Threonine"],
    "Tryptophan":    ["L-Tryptophan"],
    "Tyrosine":      ["L-Tyrosine"],
    "Valine":        ["L-Valine"],
    "GABA":          ["gamma-Aminobutyric acid"],
    "Cystathionine": ["L-Cystathionine"],
    "beta-Alanine":  ["β-Alanine", "b-Alanine"],
    "Hydroxyproline": ["4-Hydroxyproline"],

    # Neurotransmitter metabolites
    "HVA":           ["Homovanillic (HVA)"],
    "VMA":           ["Vanillylmandelic (VMA)"],
    "DOPAC":         ["Dihydroxyphenylacetic (DOPAC)"],
    "5-HIAA":        ["5-Hydroxyindoleacetic (5-HIAA)"],
    "Histamine":     ["Histamine, Plasma (ng/mL)"],
    "Serotonin":     ["Serotonin, Serum (ng/mL)"],
    "Homocysteine":  ["Homocysteine (umol/L)"],

    # Vitamins — lab-specific name variants
    "Vitamin A":     ["vitamin A, serum (labcorp) (ug/dL)", "vitamin A, retinol (quest) (ug/dL)"],
    "Vitamin D":     ["Vitamin D 25-OH", "Vitamin D 25 Hydroxy (ng/mL)"],
    "Vitamin E":     ["Vitamin E, ALPHA TOCOPHEROL (mg/dL)", "Delta Tocotrienol", "alpha-Tocopherol"],
    "Linoleic acid": ["LA (Linoleic acid)"],
    "α-Linolenic acid": ["alpha-Linolenic acid"],

    # Minerals — element names and ionic form variants
    "Fe":   ["Iron", "iron (transferrin-bound) (ug/dL)"],
    "Fe²⁺": ["Fe2+"],
    "Fe³⁺": ["Fe3+"],
    "Cu":   ["Copper", "Copper, Serum or Plasma (ug/L)"],
    "Cu²⁺": ["Cu2+"],
    "Zn":   ["Zinc", "zinc, plasma (ug/dL)"],
    "Zn²⁺": ["Zn2+", "Zn₂₊"],
    "Mg":   ["Magnesium", "magnesium, rbc (mg/dL)"],
    "Mg²⁺": ["Mg2+", "Mg₂₊"],
    "Mn":   ["Manganese", "manganese, blood (ug/L)"],
    "Mn²⁺": ["Mn2+"],
    "Se":   ["Selenium", "SELENIUM, blood (ug/L)"],
    "Ca":   ["Calcium", "Calcium Level (mg/dL)"],
    "Ca²⁺": ["Ca2+"],
}

# Build flat alias dict from groups
LABEL_ALIASES = {}
for canonical, aliases in _ALIAS_GROUPS.items():
    for alias in aliases:
        LABEL_ALIASES[alias] = canonical

# Auto-generate aliases for "Full Name (ABBREV)" patterns found in diagram labels.
# When the viewer sees "Nicotinic Acid Mononucleotide (NAMN)", it will try:
#   1. The full string (exact match in LABEL_TO_ANALYTES)
#   2. Alias lookup
#   3. Stripped versions: "Nicotinic Acid Mononucleotide" and "NAMN"
# We handle case 3 in the viewer's resolveAnalyteLabel function.


# ── CSV Parsers ──────────────────────────────────────────────────────────────

def _safe_float(s):
    """Parse a float, returning None for missing/non-numeric values."""
    if not s or s.strip() in ("", "?"):
        return None
    s = s.strip()
    # Handle ">X" and "<X" prefixes — return the numeric portion
    if s.startswith(">") or s.startswith("<"):
        try:
            return float(s[1:].replace(",", ""))
        except ValueError:
            return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def parse_theriome(path):
    """Parse theriome_aristotle.csv → dict keyed by Analyte name.
    Returns {analyte: {date, value, low, high, deviation, status}}"""
    result = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            name = row["Analyte"].strip()
            result[name] = {
                "date": "2026-02-02",  # Theriome CSV is single-timepoint; no date column
                "value": _safe_float(row["Value"]),
                "refLow": _safe_float(row["Low"]),
                "refHigh": _safe_float(row["High"]),
                "deviation": _safe_float(row.get("Deviation%")),
                "status": row.get("Status", "").strip() or "Normal",
            }
    return result


def parse_oat(path):
    """Parse mosaic_organic_acids.csv → dict keyed by marker name.
    Returns {name: {refLow, refHigh, refMean, unit, is_low_good, notes, history: [...]}}"""
    result = {}
    # Detect date columns from header
    with open(path) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        dates = []
        for h in headers:
            m = re.match(r"val_(\d{4})_(\d{2})_(\d{2})", h)
            if m:
                dates.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")

        for row in reader:
            name = row["name"].strip()
            history = []
            for date in dates:
                date_key = "val_" + date.replace("-", "_")
                status_key = "status_" + date.replace("-", "_")
                val = _safe_float(row.get(date_key))
                status = row.get(status_key, "").strip()
                if val is not None:
                    history.append({"date": date, "value": val, "status": status or "Normal"})

            result[name] = {
                "refLow": _safe_float(row.get("ref_low_normal")),
                "refHigh": _safe_float(row.get("ref_high_normal")),
                "refMean": _safe_float(row.get("ref_mean")),
                "unit": "mmol/mol creatinine",
                "is_low_good": row.get("is_low_good", "").strip().lower() == "true",
                "notes": row.get("notes", "").strip(),
                "group": row.get("group", "").strip(),
                "history": history,
            }
    return result


def parse_vibrant(path):
    """Parse vibrant CSV (wide format with date columns) → dict keyed by (Analyte, Sample_Type).
    Returns {(analyte, sample_type): {refLow, refHigh, unit, history: [{date, value}]}}"""
    result = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        # Date columns are those matching YYYY-MM-DD
        date_cols = [h for h in headers if re.match(r"\d{4}-\d{2}-\d{2}", h)]

        for row in reader:
            name = row["Analyte"].strip()
            sample = row["Sample_Type"].strip()
            ref_low = _safe_float(row.get("Ref_Low"))
            ref_high = _safe_float(row.get("Ref_High"))
            unit = row.get("Unit", "").strip()

            history = []
            for date in date_cols:
                val = _safe_float(row.get(date))
                if val is not None:
                    history.append({"date": date, "value": val})

            result[(name, sample)] = {
                "refLow": ref_low,
                "refHigh": ref_high,
                "unit": unit,
                "history": history,
            }
    return result


def parse_labcorp(path):
    """Parse labcorp.csv → dict keyed by test_name.
    Returns {test_name: {unit, refLow, refHigh, history: [{date, value, status}]}}"""
    result = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            name = row["test_name"].strip()
            val = _safe_float(row.get("value"))
            date = row.get("date", "").strip()
            if not date or val is None:
                continue
            ref_low = _safe_float(row.get("normal_low"))
            ref_high = _safe_float(row.get("normal_high"))

            if name not in result:
                # Extract unit from test_name if in parens, e.g. "Calcium Level (mg/dL)"
                unit = ""
                m = re.search(r'\(([^)]+)\)', name)
                if m:
                    unit = m.group(1)
                result[name] = {
                    "refLow": ref_low,
                    "refHigh": ref_high,
                    "unit": unit,
                    "history": [],
                }

            status = "Normal"
            if ref_low is not None and val < ref_low:
                status = "Low"
            elif ref_high is not None and val > ref_high:
                status = "High"
            result[name]["history"].append({"date": date, "value": val, "status": status})

    # Sort history by date
    for entry in result.values():
        entry["history"].sort(key=lambda h: h["date"])
    return result


def parse_cma(path):
    """Parse css_cellular_micronutrient_assay.csv → dict keyed by analyte name.
    Returns {analyte: {category, history: [{date, value}]}}"""
    result = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        date_cols = [h for h in headers if re.match(r"\d{4}-\d{2}-\d{2}", h)]
        for row in reader:
            name = row["analyte"].strip()
            history = []
            for date in date_cols:
                val = _safe_float(row.get(date))
                if val is not None:
                    history.append({"date": date, "value": val})
            result[name] = {
                "category": row.get("category", "").strip(),
                "history": history,
            }
    return result


# ── Status computation ───────────────────────────────────────────────────────

def _round_sig(x, sig=3):
    """Round a float to sig significant figures. Returns None for None."""
    if x is None:
        return None
    if x == 0:
        return 0
    return round(x, sig - 1 - int(math.floor(math.log10(abs(x)))))


def _compute_status(value, ref_low, ref_high):
    """Compute a simple status string from value and ref range."""
    if value is None or ref_low is None or ref_high is None:
        return "Unknown"
    if value > ref_high:
        return "High"
    if value < ref_low:
        return "Low"
    return "Normal"


# ── Main builder ─────────────────────────────────────────────────────────────

def build_analyte_data(test_data_dir):
    """Build the complete analyte data dict for all mapped node labels.

    Returns: {
        label: {
            "datasets": [
                {
                    "label": "Source — Description",
                    "unit": "...",
                    "refLow": float, "refHigh": float, "refMean": float|null,
                    "note": "..." or null,
                    "history": [{"date": "YYYY-MM-DD", "value": float, "status": "..."}]
                }, ...
            ]
        }
    }
    """
    # Parse all CSVs
    data_dir = Path(test_data_dir)
    theriome_path = data_dir / "theriome_aristotle.csv"
    oat_path = data_dir / "mosaic_organic_acids.csv"
    vibrant_path = data_dir / "vibrant_micronutrients.csv"
    cma_path = data_dir / "css_cellular_micronutrient_assay.csv"
    labcorp_path = data_dir / "labcorp.csv"

    theriome = parse_theriome(theriome_path) if theriome_path.exists() else {}
    oat = parse_oat(oat_path) if oat_path.exists() else {}
    vibrant = parse_vibrant(vibrant_path) if vibrant_path.exists() else {}
    cma = parse_cma(cma_path) if cma_path.exists() else {}
    labcorp = parse_labcorp(labcorp_path) if labcorp_path.exists() else {}

    result = {}

    for label, mappings in LABEL_TO_ANALYTES.items():
        datasets = []

        for source, analyte_key, note in mappings:
            if source == "theriome":
                entry = theriome.get(analyte_key)
                if not entry:
                    continue
                datasets.append({
                    "label": "Theriome — Whole Blood Metabolomics",
                    "analyte": analyte_key,
                    "unit": "arbitrary units",
                    "refLow": entry["refLow"],
                    "refHigh": entry["refHigh"],
                    "refMean": None,
                    "note": note,
                    "history": [{
                        "date": entry["date"],
                        "value": entry["value"],
                        "status": entry["status"],
                    }],
                })

            elif source == "oat":
                entry = oat.get(analyte_key)
                if not entry:
                    continue
                datasets.append({
                    "label": f"OAT — {entry['group']}" if entry.get("group") else "OAT — Urine Organic Acids",
                    "analyte": analyte_key,
                    "unit": entry["unit"],
                    "refLow": _round_sig(entry["refLow"]),
                    "refHigh": _round_sig(entry["refHigh"]),
                    "refMean": _round_sig(entry["refMean"]),
                    "note": note or entry.get("notes") or None,
                    "history": entry["history"],
                })

            elif source == "vibrant":
                # Vibrant can have multiple sample types (Serum, WBC, RBC)
                matched = [(k, v) for k, v in vibrant.items() if k[0] == analyte_key]
                for (name, sample_type), entry in matched:
                    if not entry["history"]:
                        continue
                    history = []
                    for h in entry["history"]:
                        status = _compute_status(h["value"], entry["refLow"], entry["refHigh"])
                        history.append({"date": h["date"], "value": h["value"], "status": status})
                    datasets.append({
                        "label": f"Vibrant Micronutrients — {sample_type}",
                        "analyte": analyte_key,
                        "unit": entry["unit"],
                        "refLow": entry["refLow"],
                        "refHigh": entry["refHigh"],
                        "refMean": None,
                        "note": note,
                        "history": history,
                    })

            elif source == "labcorp":
                entry = labcorp.get(analyte_key)
                if not entry:
                    continue
                datasets.append({
                    "label": "LabCorp",
                    "analyte": analyte_key,
                    "unit": entry["unit"],
                    "refLow": entry["refLow"],
                    "refHigh": entry["refHigh"],
                    "refMean": None,
                    "note": note,
                    "history": entry["history"],
                })

            elif source == "cma":
                entry = cma.get(analyte_key)
                if not entry:
                    continue
                # CMA: higher % = greater deficiency. 100 = ideal, 110 = borderline, 120+ = severely low
                datasets.append({
                    "label": "CMA — WBC",
                    "analyte": analyte_key,
                    "unit": "%",
                    "yMin": 95,
                    "refLow": None,
                    "refHigh": 110,
                    "refMean": 100,
                    "note": note or "Higher % = greater deficiency. 100 = ideal, 110 = borderline, 120+ = severely low.",
                    "history": [
                        {"date": h["date"], "value": h["value"],
                         "status": "Low" if h["value"] >= 120 else ("Low" if h["value"] > 110 else "Normal")}
                        for h in entry["history"]
                    ],
                })

        if datasets:
            result[label] = {"datasets": datasets}

    # Also build the alias index so the viewer can resolve alternate names
    result["_aliases"] = LABEL_ALIASES

    return result


def build_all_analytes(test_data_dir):
    """Build a complete list of every analyte from every source, grouped by source.

    Returns: {
        "sources": [
            {
                "name": "OAT — Urine Organic Acids",
                "analytes": [
                    {
                        "name": "Citric",
                        "datasets": [{ same format as build_analyte_data datasets }]
                    }, ...
                ]
            }, ...
        ]
    }
    """
    data_dir = Path(test_data_dir)
    theriome_path = data_dir / "theriome_aristotle.csv"
    oat_path = data_dir / "mosaic_organic_acids.csv"
    vibrant_path = data_dir / "vibrant_micronutrients.csv"
    cma_path = data_dir / "css_cellular_micronutrient_assay.csv"
    labcorp_path = data_dir / "labcorp.csv"

    sources = []

    # OAT
    if oat_path.exists():
        oat = parse_oat(oat_path)
        analytes = []
        for name, entry in sorted(oat.items()):
            if not entry["history"]:
                continue
            analytes.append({
                "name": name,
                "datasets": [{
                    "label": f"OAT — {entry['group']}" if entry.get("group") else "OAT",
                    "analyte": name,
                    "unit": entry["unit"],
                    "refLow": _round_sig(entry["refLow"]),
                    "refHigh": _round_sig(entry["refHigh"]),
                    "refMean": _round_sig(entry["refMean"]),
                    "note": entry.get("notes") or None,
                    "history": entry["history"],
                }],
            })
        sources.append({"name": "OAT — Urine Organic Acids", "analytes": analytes})

    # Theriome
    if theriome_path.exists():
        theriome = parse_theriome(theriome_path)
        analytes = []
        for name, entry in sorted(theriome.items()):
            if entry["value"] is None:
                continue
            analytes.append({
                "name": name,
                "datasets": [{
                    "label": "Theriome — Whole Blood Metabolomics",
                    "analyte": name,
                    "unit": "arbitrary units",
                    "refLow": entry["refLow"],
                    "refHigh": entry["refHigh"],
                    "refMean": None,
                    "note": None,
                    "history": [{"date": entry["date"], "value": entry["value"], "status": entry["status"]}],
                }],
            })
        sources.append({"name": "Theriome — Whole Blood Metabolomics", "analytes": analytes})

    # Vibrant
    if vibrant_path.exists():
        vibrant = parse_vibrant(vibrant_path)
        analytes = []
        seen = set()
        for (name, sample_type), entry in sorted(vibrant.items()):
            if not entry["history"]:
                continue
            display_name = f"{name} ({sample_type})"
            if display_name in seen:
                continue
            seen.add(display_name)
            history = []
            for h in entry["history"]:
                status = _compute_status(h["value"], entry["refLow"], entry["refHigh"])
                history.append({"date": h["date"], "value": h["value"], "status": status})
            analytes.append({
                "name": display_name,
                "datasets": [{
                    "label": f"Vibrant Micronutrients — {sample_type}",
                    "analyte": name,
                    "unit": entry["unit"],
                    "refLow": entry["refLow"],
                    "refHigh": entry["refHigh"],
                    "refMean": None,
                    "note": None,
                    "history": history,
                }],
            })
        sources.append({"name": "Vibrant Micronutrients", "analytes": analytes})

    # CMA
    if cma_path.exists():
        cma = parse_cma(cma_path)
        analytes = []
        for name, entry in sorted(cma.items()):
            if not entry["history"]:
                continue
            analytes.append({
                "name": name,
                "datasets": [{
                    "label": "CMA — WBC",
                    "analyte": name,
                    "unit": "%",
                    "yMin": 95,
                    "refLow": None,
                    "refHigh": 110,
                    "refMean": 100,
                    "note": "Higher % = greater deficiency. 100 = ideal, 110 = borderline, 120+ = severely low.",
                    "history": [
                        {"date": h["date"], "value": h["value"],
                         "status": "Low" if h["value"] >= 120 else ("Low" if h["value"] > 110 else "Normal")}
                        for h in entry["history"]
                    ],
                }],
            })
        sources.append({"name": "CMA — WBC", "analytes": analytes})

    # LabCorp
    if labcorp_path.exists():
        labcorp = parse_labcorp(labcorp_path)
        analytes = []
        for name, entry in sorted(labcorp.items()):
            if not entry["history"]:
                continue
            analytes.append({
                "name": name,
                "datasets": [{
                    "label": "LabCorp",
                    "analyte": name,
                    "unit": entry["unit"],
                    "refLow": entry["refLow"],
                    "refHigh": entry["refHigh"],
                    "refMean": None,
                    "note": None,
                    "history": entry["history"],
                }],
            })
        sources.append({"name": "LabCorp", "analytes": analytes})

    return {"sources": sources}
