"""Canonical LeadHunter constants shared by every interface and service."""
APP_BUSINESS_TYPES = [
    ("🦷 Dental / Dentist","dental"),("🏥 Hospital","hospital"),("🩺 Clinic","clinic"),
    ("🍽️ Restaurant","restaurant"),("☕ Cafe","cafe"),("🥐 Bakery","bakery"),
    ("🏨 Hotel","hotel"),("🌴 Resort","resort"),("🎓 School","school"),("🏫 College","college"),
    ("🎓 University","university"),("💊 Pharmacy","pharmacy"),("🏋️ Gym / Fitness","gym"),
    ("💇 Salon","salon"),("💄 Beauty","beauty"),("🚗 Car Dealer","car dealer"),
    ("🔧 Car Repair","car repair"),("🚿 Car Wash","car wash"),("🏠 Real Estate","real estate"),
    ("⚖️ Lawyer","lawyer"),("🧾 Accountant","accountant"),("✈️ Travel Agency","travel agency"),
    ("📱 Electronics","electronics"),("👕 Clothing","clothing"),("🛋️ Furniture","furniture"),
    ("💎 Jewellery","jewellery"),("🛒 Supermarket","supermarket"),("🔨 Hardware","hardware"),
    ("🏦 Bank","bank"),("🛡️ Insurance","insurance"),("🏛️ Architect","architect"),
    ("🏗️ Construction","construction"),("🖨️ Printing","printing"),("📸 Photographer","photographer"),
    ("⛽ Fuel Station","fuel"),("🐾 Veterinary","veterinary"),
]
BUSINESS_TYPES = APP_BUSINESS_TYPES
BUSINESS_TYPE_KEYS = {v for _, v in BUSINESS_TYPES}
CITIES = [
    "Bhopal","Indore","Jabalpur","Gwalior","Ujjain","Sagar","Rewa","Satna","Dewas","Ratlam",
    "Burhanpur","Khandwa","Chhindwara","Vidisha","Shivpuri","Morena","Singrauli","Damoh","Mandsaur",
    "Neemuch","Sehore","Betul","Itarsi","Narmadapuram","Khargone","Barwani","Dhar","Datia","Bhind",
    "Balaghat","Chhatarpur","Tikamgarh","Panna","Raisen","Rajgarh","Shajapur","Agar Malwa","Alirajpur",
    "Anuppur","Ashoknagar","Dindori","Harda","Jhabua","Katni","Mandla","Narsinghpur","Sheopur","Sidhi","Umaria",
]
PIPELINE_STATUSES = [
    "NEW","RESEARCHED","QUALIFIED","CONTACTED","RESPONDED","MEETING",
    "PROPOSAL","NEGOTIATION","WON","LOST","NOT_INTERESTED","DO_NOT_CONTACT",
]
STATUS_RANK = {s:i for i,s in enumerate(PIPELINE_STATUSES)}
SERVICE_NAMES = ["SEO","GEO","AEO","Google Business Profile","EPR","Websites","Automations","AI Integration","Custom Software","BigQuery","Cloud"]
