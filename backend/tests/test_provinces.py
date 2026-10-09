import pytest

from sajobs.provinces import PROVINCES, normalize_province, resolve_location


@pytest.mark.parametrize(
    "location, expected",
    [
        ("Sandton, Johannesburg", "Gauteng"),
        ("Midrand", "Gauteng"),
        ("Randburg, Gauteng", "Gauteng"),
        ("Centurion", "Gauteng"),
        ("City of Tshwane", "Gauteng"),
        ("Kempton Park, Ekurhuleni", "Gauteng"),
        ("Stellenbosch", "Western Cape"),
        ("Bellville, Cape Town", "Western Cape"),
        ("Century City", "Western Cape"),
        ("Umhlanga Rocks", "KwaZulu-Natal"),
        ("Pietermaritzburg", "KwaZulu-Natal"),
        ("Durban, KZN", "KwaZulu-Natal"),
        ("Gqeberha", "Eastern Cape"),
        ("Port Elizabeth", "Eastern Cape"),
        ("East London", "Eastern Cape"),
        ("Bloemfontein", "Free State"),
        ("Polokwane", "Limpopo"),
        ("Nelspruit", "Mpumalanga"),
        ("Mbombela", "Mpumalanga"),
        ("Rustenburg", "North West"),
        ("Kimberley", "Northern Cape"),
        ("South Africa", "Unknown"),
        (None, "Unknown"),
        ("Remote", "Remote"),
        ("Work from home, South Africa", "Remote"),
    ],
)
def test_resolve_from_display_name(location, expected):
    assert resolve_location(location)[0] == expected


def test_area_list_wins_and_city_is_most_specific():
    province, city, remote = resolve_location(
        "Sandton, Johannesburg", ["South Africa", "Gauteng", "Johannesburg", "Sandton"]
    )
    assert (province, city, remote) == ("Gauteng", "Sandton", False)


def test_area_without_province_uses_cities():
    assert resolve_location("Somewhere", ["South Africa", "Durban"]) == ("KwaZulu-Natal", "Durban", False)


def test_remote_title_keeps_real_province():
    assert resolve_location("Cape Town", [], title="Remote Data Engineer") == ("Western Cape", "Cape Town", True)


def test_unknown_city_kept_as_city():
    assert resolve_location("Smallville", []) == ("Unknown", "Smallville", False)


@pytest.mark.parametrize(
    "value, expected",
    [("gauteng", "Gauteng"), ("KZN", "KwaZulu-Natal"), ("western  cape", "Western Cape"), ("remote", "Remote"),
     ("Unknown", "Unknown"), ("Atlantis", None), (None, None), (5, None)],
)
def test_normalize_province(value, expected):
    assert normalize_province(value) == expected


def test_province_list():
    assert len(PROVINCES) == 11
