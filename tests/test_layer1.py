import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layer1_classify import classify, load_dictionary  # noqa: E402

D = load_dictionary()


def c(text):
    return classify(text, D)


# --- bill_whole: exact, case variant, encoding repair -----------------------
def test_bill_whole_exact():
    assert c("całość projektu ustawy") == "bill_whole"


def test_bill_whole_case_variant():
    assert c("Całość projektu ustawy") == "bill_whole"


def test_bill_whole_repair_calość():
    assert c("calość projektu ustawy") == "bill_whole"


def test_bill_whole_prefix_extended():
    assert c("całość projektu ustawy budżetowej na 2025") == "bill_whole"


# --- resolution_whole --------------------------------------------------------
def test_resolution_whole():
    assert c("całość projektu uchwały") == "resolution_whole"


def test_resolution_whole_case_variant():
    assert c("Całość projektu uchwały") == "resolution_whole"


# --- first_reading_rejection: order matters vs rejection ---------------------
def test_first_reading_rejection_i():
    assert c("wniosek o odrzucenie projektu ustawy w I czytaniu") == "first_reading_rejection"


def test_first_reading_rejection_pierwszym():
    assert c("wniosek o odrzucenie projektu ustawy w pierwszym czytaniu") == "first_reading_rejection"


def test_first_reading_rejection_word_order():
    assert c("wniosek o odrzucenie w pierwszym czytaniu projektu ustawy") == "first_reading_rejection"


def test_first_reading_rejection_case_variant():
    assert c("Wniosek o odrzucenie projektu ustawy w pierwszym czytaniu") == "first_reading_rejection"


def test_second_reading_is_not_first_reading():
    assert c("wniosek o odrzucenie poprawki Senatu w II czytaniu") == "rejection"


def test_iii_reading_is_not_first_reading():
    assert c("wniosek o odrzucenie sprawozdania w III czytaniu") == "rejection"


# --- rejection ---------------------------------------------------------------
def test_rejection_komisji():
    assert c("wniosek Komisji o odrzucenie projektu ustawy") == "rejection"


def test_rejection_informacji():
    assert c("wniosek o odrzucenie informacji") == "rejection"


def test_rejection_poprawki_senatu():
    assert c("wniosek o odrzucenie poprawki Senatu") == "rejection"


def test_rejection_plain():
    assert c("wniosek o odrzucenie") == "rejection"


# --- committee_composition ---------------------------------------------------
def test_committee_composition():
    assert c("wniosek w sprawie zmian w składach osobowych komisji sejmowych") == "committee_composition"


def test_committee_composition_prezydium():
    assert c("wniosek Prezydium Sejmu w sprawie zmian w składach osobowych komisji sejmowych") == "committee_composition"


# --- election ----------------------------------------------------------------
def test_election_wyboru_komisji():
    assert c("wniosek w sprawie wyboru nowego składu osobowego Komisji do Spraw Unii Europejskiej") == "election"


def test_election_nad_wyborem():
    assert c("nad wyborem sędziego Trybunału Stanu") == "election"


# --- wotum / re_enactment ----------------------------------------------------
def test_wotum_nieufności():
    assert c("wniosek o wyrażenie wotum nieufności") == "wotum"


def test_re_enactment():
    assert c("wniosek o ponowne uchwalenie ustawy") == "re_enactment"


# --- unspecified / fallback --------------------------------------------------
def test_wniosek_z_druku_is_unspecified():
    assert c("wniosek z druku nr 123") == "unspecified"


def test_procedural_motion_ii_czytanie_is_unspecified():
    # documented: no bucket in v0.1-draft; future extension via versioned change
    assert c("wniosek o niezwłoczne przystąpienie do II czytania") == "unspecified"


def test_none_is_unspecified():
    assert c(None) == "unspecified"


def test_empty_and_dash_are_unspecified():
    assert c("") == "unspecified"
    assert c("-") == "unspecified"


def test_dictionary_is_draft():
    assert D["version"].endswith("-draft")
    assert "may not be published" in D["status"]


# --- election: accented forms (review finding: confirmed false negatives) ----
def test_election_wybor_accented():
    assert c("wybór posła na rzecznika praw obywatelskich") == "election"


def test_election_wybor_accented_midstring():
    assert c("Głosowanie na listę (wybór 4 z 6 kandydatów)") == "election"


def test_election_wyboru_unaccented():
    assert c("wyboru nowego składu osobowego komisji dokonano") == "election"


def test_kodeks_wyborczy_is_not_election():
    assert c("wniosek o odrzucenie ustawy - Kodeks wyborczy") == "rejection"


def test_poprawka_kodeks_wyborczy_is_unspecified():
    assert c("poprawka do ustawy - Kodeks wyborczy") == "unspecified"


# --- resolution variants ------------------------------------------------------
def test_resolution_rezolucja():
    assert c("całość projektu rezolucji") == "resolution_whole"


def test_resolution_uchwaly_l_variant():
    assert c("całość projektu uchwaly") == "resolution_whole"


# --- repair map: case variants of the source artifact -------------------------
def test_calość_capital_c_variant():
    assert c("Calość projektu ustawy") == "bill_whole"


def test_repair_does_not_touch_correct_forms():
    assert c("całość projektu ustawy o wyborach samorządowych") == "bill_whole"


# --- rule 1 anchor: plain I-czytanie formula ----------------------------------
def test_first_reading_rejection_plain_i():
    assert c("wniosek o odrzucenie w I czytaniu") == "first_reading_rejection"


# --- rule-order edges pinned (CODEBOOK section 10: act-dominant axis) ---------
def test_order_edge_rejection_vs_committee():
    # act-dominant: the rejection motion wins over the committee subject
    assert c("wniosek o odrzucenie zmian w składach osobowych komisji") == "rejection"


def test_order_edge_odwołanie_i_wybór():
    # mixed action: rule order resolves (election precedes dismissal)
    assert c("wniosek o odwołanie i wybór następcy") == "election"


def test_order_edge_resolution_with_appointment():
    assert c("całość projektu uchwały o powołaniu członków komisji") == "resolution_whole"


def test_package_vote_exclusion():
    # mid-string "całość projektu ustaw" is deliberately NOT bill_whole (prefix)
    assert c("poprawki, całość projektu ustawy") == "unspecified"


# --- dictionary structure ------------------------------------------------------
def test_dictionary_structure():
    assert len(D["rules"]) == 13
    buckets = {r["bucket"] for r in D["rules"]}
    assert buckets == {"first_reading_rejection", "rejection", "committee_composition",
                       "bill_whole", "resolution_whole", "election", "wotum",
                       "re_enactment", "appointment", "dismissal"}
    assert {r["match"] for r in D["rules"]} <= {"contains", "prefix"}
    assert D["fallback"] == "unspecified"
    assert D["normalization"]["repairs"] == [["calość", "całość"], ["ccałość", "całość"]]
