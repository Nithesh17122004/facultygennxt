"""Idempotent reference data seed for states, cities, academic taxonomy and FAQs.

Production-safe: only reference data is created. All core recruitment features
are free, so no plans or pricing data are seeded.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.core.models import City, FAQ, State
from apps.jobs.models import Department, Designation

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

DEPARTMENTS = [
    ("Computer Science", "bi-cpu"),
    ("Information Technology", "bi-hdd-network"),
    ("Electronics and Communication Engineering", "bi-broadcast"),
    ("Electrical Engineering", "bi-lightning-charge"),
    ("Mechanical Engineering", "bi-gear"),
    ("Civil Engineering", "bi-building"),
    ("Chemical Engineering", "bi-droplet"),
    ("Mathematics", "bi-calculator"),
    ("Physics", "bi-atom"),
    ("Chemistry", "bi-flask"),
    ("Biology", "bi-tree"),
    ("Biotechnology", "bi-bezier2"),
    ("Environmental Science", "bi-globe-americas"),
    ("Commerce", "bi-graph-up-arrow"),
    ("Economics", "bi-cash-coin"),
    ("Management", "bi-briefcase"),
    ("English", "bi-book"),
    ("Hindi", "bi-journal-text"),
    ("History", "bi-bank"),
    ("Political Science", "bi-people"),
    ("Sociology", "bi-person-lines-fill"),
    ("Psychology", "bi-lightbulb"),
    ("Education", "bi-mortarboard"),
    ("Law", "bi-shield-check"),
    ("Pharmacy", "bi-capsule"),
    ("Architecture", "bi-rulers"),
    ("Design", "bi-palette"),
    ("Agriculture", "bi-flower1"),
    ("Library Science", "bi-book-half"),
]

DESIGNATIONS = [
    ("Assistant Professor", "teaching"),
    ("Associate Professor", "teaching"),
    ("Professor", "teaching"),
    ("Guest Faculty", "teaching"),
    ("Visiting Faculty", "teaching"),
    ("Adjunct Faculty", "teaching"),
    ("Dean", "teaching"),
    ("Head of Department", "teaching"),
    ("Principal", "teaching"),
    ("Director", "teaching"),
    ("Research Scientist", "research"),
    ("Postdoctoral Fellow", "research"),
    ("Junior Research Fellow", "research"),
    ("Senior Research Fellow", "research"),
    ("Research Associate", "research"),
    ("Lab Technician", "non_teaching"),
    ("Librarian", "non_teaching"),
    ("Registrar", "non_teaching"),
    ("Administrative Officer", "non_teaching"),
    ("Placement Officer", "non_teaching"),
]

FAQS = [
    (
        "How does FacultyNxtGen verify institutions?",
        "Every institution submits its official website, institutional email, contact details and an authorisation letter. Our team checks these against public records and may contact the institution directly. Only verified institutions can publish vacancies.",
        "Verification",
    ),
    (
        "Are all vacancies on FacultyNxtGen verified?",
        "Institutions must be verified before posting, and each vacancy passes a checklist review covering the official notification, deadline, eligibility and application route. If you see something that looks wrong, use the report link on the vacancy.",
        "Verification",
    ),
    (
        "Does FacultyNxtGen charge candidates?",
        "No. Creating a candidate account, saving jobs, setting alerts and applying through FacultyNxtGen are free for candidates. Never pay anyone who asks for money to secure a vacancy through this platform.",
        "Candidates",
    ),
    (
        "How do external applications work?",
        "Some institutions accept applications only through their own portal or email. The vacancy page explains this before you continue, and the official application route is shown clearly. A FacultyNxtGen record does not replace the institution's own application.",
        "Applications",
    ),
    (
        "Can I apply to a vacancy after the deadline?",
        "No. Deadlines are set from the official notification and applications close automatically. If the institution re-advertises the role, a new listing will appear with the updated dates.",
        "Applications",
    ),
    (
        "How are my documents stored?",
        "Candidate documents are stored privately and are never served from a public URL. Recruiters can access only the documents attached to applications for their institution, through short-lived signed links. You can delete documents you no longer need.",
        "Privacy",
    ),
    (
        "How do I report a suspicious vacancy?",
        "Open the vacancy and choose “Report this vacancy”. Give as much detail as you can, including the official source if available. Our team reviews reports and can suspend listings while investigating.",
        "Trust and safety",
    ),
    (
        "How do institutions advertise a vacancy?",
        "Verified institutions can post vacancies free from their dashboard. Every vacancy goes through the same verification review, and all core recruitment features are available without payment.",
        "Institutions",
    ),
    (
        "Can I export or delete my data?",
        "Yes. Candidate accounts include a data export and an account deletion request flow. Some records, such as application history, may be retained for the period required by law before deletion or anonymisation.",
        "Privacy",
    ),
    (
        "What should I do if I forget my password?",
        "Use the “Forgot password” link on the sign-in page. Reset links are sent only to the registered email address and expire automatically. FacultyNxtGen will never ask for your password or one-time code by email or phone.",
        "Account",
    ),
]

class Command(BaseCommand):
    help = "Create or refresh reference data (states, cities, departments, designations, FAQs)."

    @transaction.atomic
    def handle(self, *args, **options):
        state_count = 0
        city_count = 0
        for name, code, cities in STATES:
            state, _ = State.objects.update_or_create(
                code=code,
                defaults={"name": name, "slug": slugify(name), "is_active": True},
            )
            state_count += 1
            for city_name in cities:
                City.objects.update_or_create(
                    state=state,
                    slug=slugify(city_name),
                    defaults={"name": city_name, "is_active": True},
                )
                city_count += 1

        department_count = 0
        for order, (name, icon) in enumerate(DEPARTMENTS, start=1):
            Department.objects.update_or_create(
                slug=slugify(name),
                defaults={"name": name, "icon": icon, "is_active": True, "sort_order": order},
            )
            department_count += 1

        designation_count = 0
        for order, (name, category) in enumerate(DESIGNATIONS, start=1):
            Designation.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "category": category,
                    "is_active": True,
                    "sort_order": order,
                },
            )
            designation_count += 1

        faq_count = 0
        for order, (question, answer, category) in enumerate(FAQS, start=1):
            FAQ.objects.update_or_create(
                question=question,
                defaults={
                    "answer": answer,
                    "category": category,
                    "sort_order": order,
                    "is_published": True,
                },
            )
            faq_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Reference data ready: {state_count} states/UTs, {city_count} cities, "
                f"{department_count} departments, {designation_count} designations, "
                f"{faq_count} FAQs."
            )
        )
