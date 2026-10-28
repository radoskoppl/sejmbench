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
