import pytest
from typing import List
from zomato_recsys.data.models import Restaurant

@pytest.fixture
def sample_raw_rows() -> List[dict]:
    return [
        {
            "name": "Jassi De Paranthe",
            "listed_in(city)": "Bangalore",
            "location": "Koramangala 5th Block",
            "address": "15, 17th Main Road, Koramangala 5th Block, Bangalore",
            "url": "https://www.zomato.com/bangalore/jassi-de-paranthe-koramangala-5th-block",
            "rate": "4.1/5",
            "votes": "100",
            "cuisines": "North Indian, Punjabi",
            "approx_cost(for two people)": "400",
            "online_order": "Yes",
            "book_table": "No"
        },
        {
            "name": "Corner House Ice Creams",
            "listed_in(city)": "Bangalore",
            "location": "Indiranagar",
            "address": "Indiranagar, Bangalore",
            "url": "https://www.zomato.com/bangalore/corner-house-ice-creams-indiranagar",
            "rate": "4.6/5",
            "votes": "2400",
            "cuisines": "Desserts, Ice Cream",
            "approx_cost(for two people)": "250",
            "online_order": "Yes",
            "book_table": "No"
        },
        {
            "name": "The Black Pearl",
            "listed_in(city)": "Bangalore",
            "location": "Koramangala 5th Block",
            "address": "Koramangala, Bangalore",
            "url": "https://www.zomato.com/bangalore/the-black-pearl-koramangala",
            "rate": "4.3/5",
            "votes": "5000",
            "cuisines": "North Indian, European, Mediterranean",
            "approx_cost(for two people)": "1400",
            "online_order": "No",
            "book_table": "Yes"
        },
        {
            "name": "Toit",
            "listed_in(city)": "Bangalore",
            "location": "Indiranagar",
            "address": "Indiranagar, Bangalore",
            "url": "https://www.zomato.com/bangalore/toit-indiranagar",
            "rate": "4.7/5",
            "votes": "10000",
            "cuisines": "Italian, American, Pizza",
            "approx_cost(for two people)": "1500",
            "online_order": "No",
            "book_table": "No"
        },
        {
            "name": "New Restaurant",
            "listed_in(city)": "Bangalore",
            "location": "Indiranagar",
            "address": "Indiranagar, Bangalore",
            "url": "https://www.zomato.com/bangalore/new-restaurant",
            "rate": "NEW",
            "votes": "0",
            "cuisines": "Cafe, Fast Food",
            "approx_cost(for two people)": "None",
            "online_order": "Yes",
            "book_table": "No"
        }
    ]

@pytest.fixture
def sample_restaurants() -> List[Restaurant]:
    return [
        Restaurant(
            restaurant_id="rec-1",
            name="Jassi De Paranthe",
            city="Bangalore",
            location="Koramangala 5th Block",
            address="15, Koramangala",
            cuisines=["north indian", "punjabi"],
            aggregate_rating=4.1,
            cost_for_two=400.0,
            votes=100,
            online_order="Yes",
            book_table="No"
        ),
        Restaurant(
            restaurant_id="rec-2",
            name="Corner House Ice Creams",
            city="Bangalore",
            location="Indiranagar",
            address="Indiranagar",
            cuisines=["desserts", "ice cream"],
            aggregate_rating=4.6,
            cost_for_two=250.0,
            votes=2400,
            online_order="Yes",
            book_table="No"
        ),
        Restaurant(
            restaurant_id="rec-3",
            name="The Black Pearl",
            city="Bangalore",
            location="Koramangala 5th Block",
            address="Koramangala",
            cuisines=["north indian", "european", "mediterranean"],
            aggregate_rating=4.3,
            cost_for_two=1400.0,
            votes=5000,
            online_order="No",
            book_table="Yes"
        ),
        Restaurant(
            restaurant_id="rec-4",
            name="Toit",
            city="Bangalore",
            location="Indiranagar",
            address="Indiranagar",
            cuisines=["italian", "american", "pizza"],
            aggregate_rating=4.7,
            cost_for_two=1500.0,
            votes=10000,
            online_order="No",
            book_table="No"
        ),
        Restaurant(
            restaurant_id="rec-5",
            name="New Restaurant",
            city="Bangalore",
            location="Indiranagar",
            address="Indiranagar",
            cuisines=["cafe", "fast food"],
            aggregate_rating=None,
            cost_for_two=None,
            votes=0,
            online_order="Yes",
            book_table="No"
        )
    ]
