import pytest
from zomato_recsys.data.ingestion import clean_rating, clean_cost, clean_cuisines, generate_restaurant_id
from zomato_recsys.data.catalog import InMemoryCatalog

def test_clean_rating():
    assert clean_rating("4.1/5") == 4.1
    assert clean_rating("4.1") == 4.1
    assert clean_rating("NEW") is None
    assert clean_rating("-") is None
    assert clean_rating(None) is None
    assert clean_rating("N/A") is None

def test_clean_cost():
    assert clean_cost("1,200") == 1200.0
    assert clean_cost("450") == 450.0
    assert clean_cost("-") is None
    assert clean_cost(None) is None

def test_clean_cuisines():
    assert clean_cuisines("North Indian, Chinese") == ["north indian", "chinese"]
    assert clean_cuisines("Italian") == ["italian"]
    assert clean_cuisines("") == []
    assert clean_cuisines(None) == []

def test_generate_restaurant_id():
    row = {
        "name": "Toit",
        "listed_in(city)": "Bangalore",
        "location": "Indiranagar",
        "address": "Indiranagar, Bangalore",
        "url": "https://www.zomato.com/bangalore/toit-indiranagar"
    }
    mapping = {
        "name": "name",
        "listed_in_city": "listed_in(city)",
        "location": "location",
        "address": "address",
        "url": "url"
    }
    id1 = generate_restaurant_id(row, mapping)
    id2 = generate_restaurant_id(row, mapping)
    id3 = generate_restaurant_id(row, mapping, disambiguator=1)
    
    assert id1.startswith("rec-")
    assert id1 == id2
    assert id1 != id3

def test_in_memory_catalog(sample_restaurants):
    catalog = InMemoryCatalog(sample_restaurants)
    
    # test get by id
    r = catalog.get_restaurant_by_id("rec-1")
    assert r is not None
    assert r.name == "Jassi De Paranthe"
    
    assert catalog.get_restaurant_by_id("invalid-id") is None
    
    # test get_all
    assert len(catalog.get_all()) == 5
    
    # test unique locations
    locations = catalog.get_all_locations()
    assert "Indiranagar" in locations
    assert "Koramangala 5th Block" in locations
    assert "Bangalore" in locations
    
    # test unique cuisines
    cuisines = catalog.get_all_cuisines()
    assert "north indian" in cuisines
    assert "italian" in cuisines
    assert "desserts" in cuisines
