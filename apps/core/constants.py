"""Indian states and union territories used across the platform."""
INDIAN_STATES = [
    ("Andhra Pradesh", "andhra-pradesh", "AP"),
    ("Arunachal Pradesh", "arunachal-pradesh", "AR"),
    ("Assam", "assam", "AS"),
    ("Bihar", "bihar", "BR"),
    ("Chhattisgarh", "chhattisgarh", "CG"),
    ("Goa", "goa", "GA"),
    ("Gujarat", "gujarat", "GJ"),
    ("Haryana", "haryana", "HR"),
    ("Himachal Pradesh", "himachal-pradesh", "HP"),
    ("Jharkhand", "jharkhand", "JH"),
    ("Karnataka", "karnataka", "KA"),
    ("Kerala", "kerala", "KL"),
    ("Madhya Pradesh", "madhya-pradesh", "MP"),
    ("Maharashtra", "maharashtra", "MH"),
    ("Manipur", "manipur", "MN"),
    ("Meghalaya", "meghalaya", "ML"),
    ("Mizoram", "mizoram", "MZ"),
    ("Nagaland", "nagaland", "NL"),
    ("Odisha", "odisha", "OD"),
    ("Punjab", "punjab", "PB"),
    ("Rajasthan", "rajasthan", "RJ"),
    ("Sikkim", "sikkim", "SK"),
    ("Tamil Nadu", "tamil-nadu", "TN"),
    ("Telangana", "telangana", "TS"),
    ("Tripura", "tripura", "TR"),
    ("Uttar Pradesh", "uttar-pradesh", "UP"),
    ("Uttarakhand", "uttarakhand", "UK"),
    ("West Bengal", "west-bengal", "WB"),
    ("Andaman and Nicobar Islands", "andaman-and-nicobar-islands", "AN"),
    ("Chandigarh", "chandigarh", "CH"),
    ("Dadra and Nagar Haveli and Daman and Diu", "dadra-and-nagar-haveli-and-daman-and-diu", "DH"),
    ("Delhi", "delhi", "DL"),
    ("Jammu and Kashmir", "jammu-and-kashmir", "JK"),
    ("Ladakh", "ladakh", "LA"),
    ("Lakshadweep", "lakshadweep", "LD"),
    ("Puducherry", "puducherry", "PY"),
]

STATE_NAMES = {name for name, _slug, _code in INDIAN_STATES}
STATE_SLUGS = {slug: name for name, slug, _code in INDIAN_STATES}

# A practical launch set of academic hubs. New cities can be added in the
# admin without code changes.
CITIES_BY_STATE = {
    "andhra-pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Tirupati", "Nellore", "Kurnool", "Rajahmundry"],
    "arunachal-pradesh": ["Itanagar", "Naharlagun", "Pasighat", "Tawang"],
    "assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat", "Tezpur"],
    "bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Darbhanga"],
    "chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Durg", "Rajnandgaon"],
    "goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa"],
    "gujarat": ["Ahmedabad", "Gandhinagar", "Vadodara", "Surat", "Rajkot", "Bhavnagar"],
    "haryana": ["Gurugram", "Faridabad", "Kurukshetra", "Hisar", "Rohtak", "Panipat"],
    "himachal-pradesh": ["Shimla", "Dharamshala", "Solan", "Mandi", "Kangra"],
    "jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Hazaribagh"],
    "karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Belagavi", "Dharwad", "Manipal"],
    "kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kottayam", "Kannur"],
    "madhya-pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur", "Ujjain", "Sagar"],
    "maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad", "Kolhapur", "Amravati"],
    "manipur": ["Imphal", "Thoubal", "Churachandpur"],
    "meghalaya": ["Shillong", "Tura", "Jowai"],
    "mizoram": ["Aizawl", "Lunglei", "Champhai"],
    "nagaland": ["Kohima", "Dimapur", "Mokokchung"],
    "odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Puri", "Sambalpur"],
    "punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Chandigarh"],
    "rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner"],
    "sikkim": ["Gangtok", "Namchi", "Gyalshing"],
    "tamil-nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Vellore", "Tirunelveli"],
    "telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam"],
    "tripura": ["Agartala", "Udaipur", "Dharmanagar"],
    "uttar-pradesh": ["Lucknow", "Kanpur", "Varanasi", "Prayagraj", "Agra", "Noida", "Aligarh", "Meerut"],
    "uttarakhand": ["Dehradun", "Haridwar", "Haldwani", "Nainital", "Roorkee"],
    "west-bengal": ["Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol", "Kharagpur"],
    "andaman-and-nicobar-islands": ["Port Blair"],
    "chandigarh": ["Chandigarh"],
    "dadra-and-nagar-haveli-and-daman-and-diu": ["Daman", "Silvassa", "Diu"],
    "delhi": ["New Delhi", "Delhi", "Dwarka"],
    "jammu-and-kashmir": ["Srinagar", "Jammu", "Anantnag", "Baramulla"],
    "ladakh": ["Leh", "Kargil"],
    "lakshadweep": ["Kavaratti"],
    "puducherry": ["Puducherry", "Karaikal", "Mahe"],
}

INSTITUTION_TYPES = [
    ("government", "Government"),
    ("private", "Private"),
    ("deemed", "Deemed University"),
    ("central", "Central University"),
    ("state", "State University"),
    ("autonomous", "Autonomous College"),
    ("engineering", "Engineering College"),
    ("arts_science", "Arts and Science College"),
    ("polytechnic", "Polytechnic"),
    ("other", "Other Recognised Institution"),
]

INSTITUTION_TYPE_NAMES = dict(INSTITUTION_TYPES)

EMPLOYMENT_TYPES = [
    ("full_time", "Full time"),
    ("part_time", "Part time"),
    ("contract", "Contract"),
    ("temporary", "Temporary"),
    ("visiting", "Visiting / Guest faculty"),
]

EMPLOYMENT_TYPE_NAMES = dict(EMPLOYMENT_TYPES)

JOB_CATEGORIES = [
    ("teaching", "Teaching"),
    ("research", "Research"),
    ("non_teaching", "Non-teaching"),
]

JOB_CATEGORY_NAMES = dict(JOB_CATEGORIES)

VERIFICATION_STATUSES = [
    ("pending", "Pending verification"),
    ("verified", "Verified"),
    ("rejected", "Rejected"),
    ("suspended", "Suspended"),
]

PH_D_STATUSES = [
    ("completed", "PhD completed"),
    ("pursuing", "PhD pursuing"),
    ("awarded", "PhD awarded"),
    ("not_started", "Not started"),
]

DEGREE_LEVELS = [
    ("bachelor", "Bachelor's degree"),
    ("master", "Master's degree"),
    ("mphil", "M.Phil."),
    ("phd", "PhD"),
    ("postdoc", "Postdoctoral"),
    ("other", "Other"),
]

EXPERIENCE_CHOICES = [(i, f"{i} year{'s' if i != 1 else ''}") for i in range(0, 31)]

APPLICATION_METHODS = [
    ("external", "Apply on institution website / email"),
    ("internal", "Apply through FacultyNxtGen"),
]

APPLICATION_STATUSES = [
    ("submitted", "Submitted"),
    ("under_review", "Under review"),
    ("shortlisted", "Shortlisted"),
    ("selected", "Selected"),
    ("rejected", "Not selected"),
    ("withdrawn", "Withdrawn"),
]
