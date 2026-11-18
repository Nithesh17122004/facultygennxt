"""Populate the location tables required by institution registration.

This data migration runs with Django's normal migrate command and does not
depend on Render Shell or a request-time seed operation.
"""
from django.db import migrations
from django.utils.text import slugify

STATES = [
    ("Andhra Pradesh", "AP", ["Visakhapatnam", "Vijayawada", "Guntur", "Tirupati", "Nellore", "Kakinada", "Rajahmundry"]),
    ("Arunachal Pradesh", "AR", ["Itanagar", "Naharlagun", "Pasighat", "Tawang"]),
    ("Assam", "AS", ["Guwahati", "Dibrugarh", "Silchar", "Jorhat", "Tezpur", "Nagaon"]),
    ("Bihar", "BR", ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Darbhanga", "Purnia"]),
    ("Chhattisgarh", "CG", ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Raigarh"]),
    ("Goa", "GA", ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda"]),
    ("Gujarat", "GJ", ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar", "Bhavnagar", "Jamnagar"]),
    ("Haryana", "HR", ["Gurugram", "Faridabad", "Panipat", "Ambala", "Hisar", "Rohtak", "Karnal"]),
    ("Himachal Pradesh", "HP", ["Shimla", "Dharamshala", "Mandi", "Solan", "Kullu", "Hamirpur"]),
    ("Jharkhand", "JH", ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Hazaribagh", "Deoghar"]),
    ("Karnataka", "KA", ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Dharwad", "Belagavi", "Manipal"]),
    ("Kerala", "KL", ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kannur", "Kollam", "Kottayam"]),
    ("Madhya Pradesh", "MP", ["Bhopal", "Indore", "Gwalior", "Jabalpur", "Ujjain", "Sagar", "Rewa"]),
    ("Maharashtra", "MH", ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad", "Kolhapur", "Thane", "Amravati"]),
    ("Manipur", "MN", ["Imphal", "Thoubal", "Churachandpur", "Bishnupur"]),
    ("Meghalaya", "ML", ["Shillong", "Tura", "Jowai", "Nongstoin"]),
    ("Mizoram", "MZ", ["Aizawl", "Lunglei", "Champhai", "Serchhip"]),
    ("Nagaland", "NL", ["Kohima", "Dimapur", "Mokokchung", "Tuensang"]),
    ("Odisha", "OD", ["Bhubaneswar", "Cuttack", "Rourkela", "Puri", "Sambalpur", "Berhampur"]),
    ("Punjab", "PB", ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Mohali"]),
    ("Rajasthan", "RJ", ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner", "Alwar"]),
    ("Sikkim", "SK", ["Gangtok", "Namchi", "Gyalshing", "Mangan"]),
    ("Tamil Nadu", "TN", ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli", "Vellore", "Srivilliputhur", "Virudhunagar", "Sivakasi", "Rajapalayam", "Sattur", "Kovilpatti", "Dindigul", "Erode", "Tiruppur", "Thanjavur", "Theni", "Nagercoil", "Karur", "Namakkal", "Hosur", "Cuddalore", "Kanchipuram", "Tiruvannamalai", "Thoothukudi", "Ramanathapuram", "Nagapattinam", "Krishnagiri"]),
    ("Telangana", "TS", ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam", "Secunderabad"]),
    ("Tripura", "TR", ["Agartala", "Udaipur", "Dharmanagar", "Kailashahar"]),
    ("Uttar Pradesh", "UP", ["Lucknow", "Kanpur", "Varanasi", "Agra", "Noida", "Ghaziabad", "Meerut", "Prayagraj"]),
    ("Uttarakhand", "UK", ["Dehradun", "Haridwar", "Rishikesh", "Haldwani", "Roorkee", "Nainital"]),
    ("West Bengal", "WB", ["Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol", "Kharagpur"]),
    ("Andaman and Nicobar Islands", "AN", ["Port Blair"]),
    ("Chandigarh", "CH", ["Chandigarh"]),
    ("Dadra and Nagar Haveli and Daman and Diu", "DH", ["Daman", "Silvassa", "Diu"]),
    ("Delhi", "DL", ["New Delhi", "Delhi"]),
    ("Jammu and Kashmir", "JK", ["Srinagar", "Jammu", "Anantnag", "Baramulla"]),
    ("Ladakh", "LA", ["Leh", "Kargil"]),
    ("Lakshadweep", "LD", ["Kavaratti"]),
    ("Puducherry", "PY", ["Puducherry", "Karaikal", "Mahe", "Yanam"]),
]


def populate_locations(apps, schema_editor):
    State = apps.get_model("core", "State")
    City = apps.get_model("core", "City")
    db = schema_editor.connection.alias

    for name, code, city_names in STATES:
        state, _ = State.objects.using(db).update_or_create(
            code=code,
            defaults={"name": name, "slug": slugify(name), "is_active": True},
        )
        for city_name in city_names:
            City.objects.using(db).update_or_create(
                state_id=state.pk,
                slug=slugify(city_name),
                defaults={"name": city_name, "is_active": True},
            )


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunPython(populate_locations, migrations.RunPython.noop)]
