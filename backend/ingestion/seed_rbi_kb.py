import os
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session, sessionmaker
from backend.database import SessionLocal, engine, Base
from backend.models import KnowledgeDocument, KnowledgeChunk, User
from backend.auth import get_password_hash
from backend.rag.vector_store import hybrid_vector_store
from backend.ingestion.chunker import document_chunker
from backend.ingestion.ocr_engine import ocr_engine

CURATED_RBI_DOCS = [
    {
        "title": "RBI Master Direction - Know Your Customer (KYC) Direction, 2016 (Updated 2023)",
        "notification_number": "DOR.AML.REC.48/14.01.001/2023-24",
        "publication_date": "2023-05-04",
        "effective_date": "2023-05-04",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566",
        "document_type": "pdf",
        "page_count": 42,
        "is_ocr": False,
        "text_content": """
Section 1: General & Applicability
These Directions shall be called the Reserve Bank of India (Know Your Customer (KYC)) Directions, 2016. These Directions apply to every entity Regulated by Reserve Bank of India (RE) including Scheduled Commercial Banks, Regional Rural Banks, Small Finance Banks, and Payment Banks.

Section 2: Customer Due Diligence (CDD) and Officially Valid Documents (OVD)
For undertaking Customer Due Diligence (CDD), Regulated Entities (REs) shall obtain from the customer:
1. Proof of possession of Aadhaar number (where customer desirous of receiving benefit or subsidy under Section 7 of Aadhaar Act, or voluntarily submits Aadhaar in masked form).
2. One of the six Officially Valid Documents (OVD): Passport, Driving License, Proof of possession of Aadhaar number, Voter's Identity Card issued by the Election Commission of India, Job card issued by NREGA duly signed by an officer of the State Government, or Letter issued by the National Population Register containing details of name and address.
Where the OVD furnished by the customer does not contain updated address, utility bills (electricity, telephone, post-paid mobile, piped gas) not more than two months old, property tax receipt, or pension payment orders may be accepted for limited 3-month temporary period.

Section 3: Video-based Customer Identification Process (V-CIP)
Regulated Entities (REs) may undertake live V-CIP for individual customer onboarding, proprietorship firms, and legal entities. The V-CIP process must be conducted by official bank staff located in India, using geo-tagging to ensure the customer is physically present within Indian territory. The video recording must include live interaction, capture of live photograph, and real-time verification of Aadhaar XML/e-KYC and PAN.

Section 4: Periodic Updation of KYC (Re-KYC)
Periodic updation of KYC shall be carried out at least once every 2 years for high risk customers, once every 8 years for medium risk customers, and once every 10 years for low risk customers. No fresh documents are required for low-risk customers if there is no change in KYC information; a self-declaration submitted via ATM, internet banking, mobile banking, or email is sufficient.
"""
    },
    {
        "title": "RBI Procedural Guidelines for National Electronic Funds Transfer (NEFT) System",
        "notification_number": "DPSS.CO.EPPD.No.863/04.03.01/2019-20",
        "publication_date": "2019-12-06",
        "effective_date": "2019-12-16",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11756",
        "document_type": "pdf",
        "page_count": 18,
        "is_ocr": False,
        "text_content": """
Section 1: Operating Hours and Settlement Batches
The National Electronic Funds Transfer (NEFT) system operates on a 24x7x365 basis with effect from December 16, 2019. NEFT operates in half-hourly settlement batches starting from 00:30 hours to 00:00 hours every day including weekends, Sundays, and public holidays, resulting in 48 settlement batches daily.

Section 2: Transaction Limits and Processing Timelines
There is no minimum or maximum transaction amount limit stipulated by RBI for individual NEFT transactions. Member banks may fix operational limits based on risk assessment. For cash-based remittances to Nepal under Indo-Nepal Remittance Scheme, maximum limit is ₹50,000 per transaction with maximum 12 remittances per calendar year.
Beneficiary banks must credit the beneficiary's account immediately upon settlement or return the transaction to the remitting bank within two hours of settlement batch completion (B+2 hours). If the beneficiary account cannot be credited, the funds must be returned to the originator within 2 hours.

Section 3: Charges and Penalties
With effect from July 1, 2019, RBI has waived all processing charges levied on member banks for NEFT transactions. Member banks are prohibited from levying any charges on savings bank account holders for online NEFT transactions (initiated through internet banking or mobile banking applications).
In case of delayed credit or delayed return, member banks are liable to pay penal interest at the prevailing RBI Repo Rate plus 2% to the customer for the period of delay.
"""
    },
    {
        "title": "RBI Guidelines on Real Time Gross Settlement (RTGS) System",
        "notification_number": "DPSS.CO.RTGS.No.1942/04.04.002/2019-20",
        "publication_date": "2020-12-04",
        "effective_date": "2020-12-14",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12001",
        "document_type": "pdf",
        "page_count": 22,
        "is_ocr": False,
        "text_content": """
Section 1: Round-the-Clock RTGS Operation
The Real Time Gross Settlement (RTGS) system has been made available 24x7x365 across all days of the year with effect from 00:30 hours on December 14, 2020. RTGS transactions are processed continuously on a transaction-by-transaction gross settlement basis.

Section 2: Minimum and Maximum Thresholds
The minimum transaction amount for outward customer RTGS is ₹2,00,000 (Rupees Two Lakhs). There is no upper maximum limit for RTGS transactions. Transactions below ₹2 Lakhs must be routed through NEFT or IMPS.

Section 3: Customer Service and Credit Timelines
Beneficiary banks must credit the customer account in real time, within 30 minutes of receiving the RTGS payment message. In case of credit failure, money must be returned to the remitting customer within 30 minutes. Remitting banks are prohibited from charging outward customer transactions initiated online.
"""
    },
    {
        "title": "RBI Master Direction on Regulatory Framework for Digital Lending, 2022",
        "notification_number": "RBI/2022-23/111 DOR.CRE.REC.65/21.07.001/2022-23",
        "publication_date": "2022-09-02",
        "effective_date": "2022-11-30",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12382",
        "document_type": "pdf",
        "page_count": 28,
        "is_ocr": False,
        "text_content": """
Section 1: Loan Disbursal and Repayment Flow
All loan disbursals and repayments shall be executed strictly directly between the bank account of the borrower and the Regulated Entity (RE), without any pass-through account or pool account of any Lending Service Provider (LSP) or third-party digital platform.

Section 2: Key Fact Statement (KFS) and Cooling-off Period
Regulated Entities must provide a standardized Key Fact Statement (KFS) to the borrower before loan execution. The KFS must transparently disclose the All-Inclusive Annual Percentage Rate (APR), recovery mechanisms, and grievance redressal officer contact.
Borrowers must be provided an explicit cooling-off or look-up period of at least 3 days for loans of tenor 7 days or more, and 1 day for loans of tenor less than 7 days, during which the borrower can exit the digital loan by paying the principal amount and proportionate APR without any penalty.

Section 3: Data Privacy and Storage
Lending apps are prohibited from accessing mobile phone resources such as file and media storage, contact lists, call logs, and telephony functions. A one-time access to camera, microphone, and location is permitted solely for onboarding and KYC purposes with explicit borrower consent. Data storage must reside strictly in servers located within India.
"""
    },
    {
        "title": "RBI Master Direction – Credit Card and Debit Card – Issuance and Conduct Directions, 2022",
        "notification_number": "RBI/2022-23/29 DOR.AUT.REC.No.27/24.01.041/2022-23",
        "publication_date": "2022-04-21",
        "effective_date": "2022-07-01",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12300",
        "document_type": "pdf",
        "page_count": 34,
        "is_ocr": False,
        "text_content": """
Section 1: Unsolicited Cards and Unauthorized Upgrades
Card issuers are strictly prohibited from issuing unsolicited credit cards or upgrading existing cards without explicit written or OTP-verified consent from the customer. If an unsolicited card is activated without explicit consent, the card issuer shall reverse all charges and pay a penalty to the customer equivalent to twice the value of charges levied.

Section 2: Closure of Credit Cards within 7 Days
Any request for closure of a credit card must be honored by the card issuer within 7 working days, subject to the customer clearing all outstanding dues. Failure to close the card within 7 working days shall result in a penalty of ₹500 per day of delay payable to the customer until the card is closed.

Section 3: Billing Cycle and Interest Calculation
Card issuers shall not levy late payment fees or penal charges unless the payment remains overdue past the due date by at least 3 days (grace period). Interest on revolving credit shall only be charged on the outstanding balance from the due date, not retroactively from the transaction date if partial payment was made.
"""
    },
    {
        "title": "RBI Circular on Customer Protection – Limiting Liability in Unauthorised Electronic Banking Transactions",
        "notification_number": "DBR.No.Leg.BC.78/09.07.005/2017-18",
        "publication_date": "2017-07-06",
        "effective_date": "2017-07-06",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11040",
        "document_type": "pdf",
        "page_count": 12,
        "is_ocr": False,
        "text_content": """
Section 1: Zero Customer Liability
A customer shall have Zero Liability in unauthorized electronic banking transactions where:
1. Contributory fraud/negligence/deficiency lies on the part of the bank (irrespective of whether or not the transaction is reported by the customer).
2. Third-party breach occurs where neither the bank nor the customer is at fault, and the customer notifies the bank within 3 working days of receiving the SMS/email alert from the bank.

Section 2: Limited Customer Liability (3 to 7 Days Reporting)
If the customer notifies the bank within 4 to 7 working days of receiving the SMS/email alert for a third-party breach:
- Maximum liability for Basic Savings Bank Deposit (BSBD) Accounts: ₹5,000.
- Maximum liability for all other Savings Bank accounts, prepaid instruments, and credit cards with limit up to ₹5 Lakhs: ₹10,000.
- Maximum liability for Credit cards with limit above ₹5 Lakhs and Current/Overdraft accounts: ₹25,000.
If the customer reports beyond 7 working days, the liability shall be determined in accordance with the Board-approved policy of the bank.

Section 3: Shadow Reversal Timeline
The bank must credit (shadow reversal) the disputed amount to the customer's account within 10 working days from the date of notification by the customer. The complaint must be resolved within 90 days.
"""
    },
    {
        "title": "RBI Integrated Ombudsman Scheme, 2021",
        "notification_number": "CEP.CO.PRD.No.S611/13.01.001/2021-22",
        "publication_date": "2021-11-12",
        "effective_date": "2021-11-12",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12192",
        "document_type": "pdf",
        "page_count": 26,
        "is_ocr": False,
        "text_content": """
Section 1: Scheme Objective and 'One Nation One Ombudsman'
The Reserve Bank - Integrated Ombudsman Scheme, 2021 integrates three former Ombudsman schemes into a single point of grievance redressal for customers of Scheduled Commercial Banks, RRBs, Non-Banking Financial Companies (NBFCs), and Payment System Participants.

Section 2: Eligibility and Complaint Filing Timelines
A customer can file a complaint before the Banking Ombudsman if:
1. The customer first submitted a written representation to the Regulated Entity (RE), and
2. The RE rejected the complaint, or the complainant did not receive a reply within 30 days, or the complainant is not satisfied with the reply.
The complaint must be lodged within 1 year from the date of receipt of the bank's rejection or 1 year and 30 days from the original representation.

Section 3: Compensation Powers
The Ombudsman has the power to pass an Award granting compensation up to ₹20,00,000 (Rupees Twenty Lakhs) for actual financial loss suffered by the complainant, and up to ₹1,00,000 (Rupees One Lakh) for harassment, mental agony, and loss of time.
"""
    },
    {
        "title": "RBI Master Direction on Priority Sector Lending (PSL) – Targets and Classification",
        "notification_number": "FIDD.CO.Plan.BC.5/04.09.01/2020-21",
        "publication_date": "2020-09-04",
        "effective_date": "2020-09-04",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11959",
        "document_type": "pdf",
        "page_count": 38,
        "is_ocr": False,
        "text_content": """
Section 1: Overall PSL Targets for Domestic Commercial Banks
Domestic Scheduled Commercial Banks and Foreign Banks with 20 branches and above must achieve an overall Priority Sector Lending target of 40% of Adjusted Net Bank Credit (ANBC) or Credit Equivalent Amount of Off-Balance Sheet Exposure (CEOBE), whichever is higher.

Section 2: Sub-Targets
- Agriculture Sector: 18% of ANBC, out of which at least 10% is prescribed for Small and Marginal Farmers (SMF).
- Micro Enterprises: 7.5% of ANBC.
- Advances to Weaker Sections: 12% of ANBC.

Section 3: Eligible Categories
Eligible sectors under PSL include: Agriculture, Micro Small and Medium Enterprises (MSME), Export Credit, Education, Housing, Social Infrastructure, Renewable Energy, and Others (Weaker sections, self-help groups).
"""
    },
    {
        "title": "RBI Master Direction on Housing Finance & Loan-to-Value (LTV) Ratios",
        "notification_number": "RBI/2020-21/53 DOR.No.BP.BC.24/08.12.015/2020-21",
        "publication_date": "2020-10-16",
        "effective_date": "2020-10-16",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11982",
        "document_type": "pdf",
        "page_count": 16,
        "is_ocr": False,
        "text_content": """
Section 1: Loan-to-Value (LTV) Caps for Individual Housing Loans
To ensure prudent lending and prevent overheating in the real estate market, banks must adhere to the following Loan-to-Value (LTV) limits:
1. Individual housing loans up to ₹30 Lakhs: Maximum LTV ratio of 90% (minimum 10% margin / borrower contribution).
2. Housing loans above ₹30 Lakhs and up to ₹75 Lakhs: Maximum LTV ratio of 80% (minimum 20% margin).
3. Housing loans above ₹75 Lakhs: Maximum LTV ratio of 75% (minimum 25% borrower contribution).

Section 2: Prohibition of Clubbing Stamp Duty
Banks shall not include stamp duty, registration charges, and other documentation taxes in the property cost for calculating LTV, except for low-cost affordable housing loans up to ₹10 Lakhs.
"""
    },
    {
        "title": "RBI Master Direction on Interest Rate on Rupee Deposits",
        "notification_number": "DBR.DIR.No.84/13.03.00/2015-16",
        "publication_date": "2016-03-03",
        "effective_date": "2016-03-03",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=10296",
        "document_type": "pdf",
        "page_count": 24,
        "is_ocr": False,
        "text_content": """
Section 1: Savings Bank Deposit Interest Calculation
Interest on savings bank accounts shall be calculated by banks on a daily product basis. Interest shall be credited to customer savings accounts on a quarterly basis or shorter intervals (such as monthly credit).

Section 2: Term Deposits and Differential Interest Rates
Banks are permitted to offer differential rates of interest on term deposits based on deposit size for single rupee term deposits of ₹2 Crore and above. Banks may offer an additional differential interest rate (usually 0.50% to 0.75% higher) on term deposits to Senior Citizens (individuals aged 60 years and above).

Section 3: Premature Withdrawal Penalty
Banks must disclose the penal rate for premature withdrawal of domestic term deposits in their policy. For deposits below ₹2 Crore, premature withdrawal must be permitted unless explicitly chosen as a non-callable deposit product.
"""
    },
    {
        "title": "RBI Guidelines on Fair Practices Code for Lenders",
        "notification_number": "DBOD.No.Leg.BC.91/09.07.005/2002-03",
        "publication_date": "2003-05-05",
        "effective_date": "2003-05-05",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=1148",
        "document_type": "pdf",
        "page_count": 14,
        "is_ocr": False,
        "text_content": """
Section 1: Loan Applications and Processing
Loan application forms must include necessary information affecting the borrower's interest so that a meaningful comparison can be made with terms offered by other lenders. The bank must provide an acknowledgement for all loan applications with a stipulated verification time frame.

Section 2: Loan Appraisal and Sanction Letter
Banks shall convey in writing the loan sanction terms, including the sanctioned loan amount, annualized rate of interest, method of application of interest, and penal interest terms. A copy of the loan agreement along with all enclosures must be furnished to the borrower.

Section 3: Recovery and Harassment Prohibition
In the matter of loan recovery, lenders shall not resort to undue harassment, intimidation, verbal abuse, or calling borrowers at odd hours (before 08:00 AM or after 07:00 PM).
"""
    },
    {
        "title": "RBI Master Direction on Cyber Security Framework in Banks",
        "notification_number": "DBS.CO/CSITE/BC.11/33.01.001/2015-16",
        "publication_date": "2016-06-02",
        "effective_date": "2016-06-02",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=10444",
        "document_type": "pdf",
        "page_count": 30,
        "is_ocr": False,
        "text_content": """
Section 1: Cyber Security Policy and SOC Operations
Banks must maintain a Board-approved Cyber Security Policy distinct from their general IT Policy. Banks must set up a 24x7 Security Operations Centre (SOC) to proactively monitor network events, security alerts, and anomalous electronic transactions.

Section 2: Incident Reporting to RBI within 2 to 6 Hours
All unusual cyber security incidents, data breaches, ATM hacks, ransomware attacks, and unauthorized transaction attempts must be reported to the Cyber Security and Information Technology Examination (CSITE) Cell of RBI within 2 to 6 hours of occurrence.

Section 3: Two-Factor Authentication (2FA) and Customer Alerts
Banks must enforce Two-Factor Authentication (2FA) for all remote electronic payment channels. Mandatory instant SMS and email transaction alerts must be dispatched for every debit and credit transaction.
"""
    },
    {
        "title": "RBI Circular on Inoperative Accounts and Unclaimed Deposits / DEA Fund",
        "notification_number": "RBI/2023-24/105 DOR.SOG.REC.66/13.03.000/2023-24",
        "publication_date": "2024-01-01",
        "effective_date": "2024-04-01",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12586",
        "document_type": "pdf",
        "page_count": 20,
        "is_ocr": False,
        "text_content": """
Section 1: Classification of Inoperative Accounts
A savings or current account shall be treated as inoperative / dormant if there are no customer-induced transactions in the account for a continuous period of more than 2 years. Banks are prohibited from levying penal charges for non-maintenance of minimum balance on inoperative accounts.

Section 2: Transfer to Depositor Education and Awareness (DEA) Fund
Balances in accounts that have remained unclaimed or inoperative for 10 years or more shall be transferred to the Depositor Education and Awareness (DEA) Fund maintained by the Reserve Bank of India on a monthly basis. Customers or their legal heirs can claim refund of DEA Fund amounts at any time through the bank along with applicable interest.
"""
    },
    {
        "title": "IDFC FIRST Bank Savings Account & Deposit Rules, 2024",
        "notification_number": "IDFC-RET-SAV-2024-01",
        "publication_date": "2024-02-15",
        "effective_date": "2024-02-15",
        "source": "BANK_POLICY",
        "source_url": "https://www.idfcfirstbank.com/personal-banking/accounts/savings-account",
        "document_type": "pdf",
        "page_count": 10,
        "is_ocr": False,
        "text_content": """
Section 1: Monthly Interest Credit on Savings Accounts
IDFC FIRST Bank offers Monthly Interest Credit on all Savings Accounts, allowing customers to earn compounding interest every month directly credited into their account, calculated on the daily end-of-day balance.

Section 2: Zero Fee Banking on Common Services
IDFC FIRST Bank provides Zero Fee Banking on 28+ essential services including IMPS, NEFT, RTGS, debit card issuance, ATM transactions across all bank ATMs in India, cheque book issuance, DD issuance, and duplicate statement requests, subject to maintaining the required Average Monthly Balance (AMB).

Section 3: Deposit Safety and DICGC Coverage
All deposits with IDFC FIRST Bank are insured up to ₹5,00,000 (Rupees Five Lakhs) per depositor by the Deposit Insurance and Credit Guarantee Corporation (DICGC), a wholly owned subsidiary of RBI.
"""
    },
    {
        "title": "IDFC FIRST Bank Digital Banking & FASTag Guidelines, 2024",
        "notification_number": "IDFC-DIG-FAST-2024-02",
        "publication_date": "2024-03-01",
        "effective_date": "2024-03-01",
        "source": "BANK_POLICY",
        "source_url": "https://www.idfcfirstbank.com/personal-banking/payments/fastag",
        "document_type": "pdf",
        "page_count": 8,
        "is_ocr": False,
        "text_content": """
Section 1: IDFC FIRST FASTag Issuance and Auto-Recharge
IDFC FIRST Bank FASTag is a reloadable RFID tag enabling automatic toll deduction across National and State Highways under the NETC program. Customers can link FASTag to their IDFC FIRST Bank savings account for seamless auto-recharge.

Section 2: Dispute Resolution and Toll Refund Timelines
In case of incorrect or duplicate toll deduction at toll plazas, customers can raise a chargeback dispute through the mobile banking app. As per NPCI guidelines, disputes are investigated and wrongful deductions refunded to the customer within 7 to 15 working days.
"""
    },
    {
        "title": "Scanned RBI Master Circular on Banking Codes (OCR Ambiguity Test Document)",
        "notification_number": "RBI/2024-25/0O18", # Contains 0 vs O ambiguity
        "publication_date": "2024-06-10",
        "effective_date": "2024-06-10",
        "source": "RBI",
        "source_url": "https://www.rbi.org.in/ocr-scanned-archive",
        "document_type": "scanned_pdf",
        "page_count": 4,
        "is_ocr": True,
        "text_content": """
Page 1 [OCR Scanned Text]:
NOTIFICATION NO: RBI/2024-25/0O18
SUBJECT: REGULATORY CHARGES AND TRANSACTION IDENTIFIER AUDIT
All Scheduled Commercial Banks must verify regulatory circular code RBI/2024-25/0O18.
The threshold transaction limit is fixed at ₹SO,OOO (Fifty Thousand Rupees) with a penalty interest rate of B.5% for non-compliance.
Note: Ambiguity in scanned characters 0O18 and ₹SO,OOO requires manual verification against physical register.
"""
    }
]

def seed_database_and_vector_store(custom_engine=None, custom_session=None):
    """Initializes tables, creates default admin/demo users, and seeds curated RBI/IDFC documents."""
    active_engine = custom_engine or engine
    Base.metadata.create_all(bind=active_engine)
    db: Session = custom_session if custom_session else (sessionmaker(autocommit=False, autoflush=False, bind=active_engine))()

    try:
        # 1. Create Default Users if not existing
        admin_email = "admin@idfcbank.com"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                name="IDFC Bank Admin",
                password_hash=get_password_hash("Admin@12345"),
                role="admin",
                auth_provider="local"
            )
            db.add(admin)

        demo_user_email = "customer@idfcbank.com"
        demo_user = db.query(User).filter(User.email == demo_user_email).first()
        if not demo_user:
            demo_user = User(
                email=demo_user_email,
                name="Siddharth Sharma",
                password_hash=get_password_hash("Customer@123"),
                role="user",
                auth_provider="local"
            )
            db.add(demo_user)

        db.commit()

        # 2. Seed Curated Documents
        all_chunks_for_index = []

        for doc_data in CURATED_RBI_DOCS:
            checksum = hashlib.sha256(doc_data["text_content"].encode("utf-8")).hexdigest()
            existing_doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.checksum == checksum).first()

            if not existing_doc:
                # Detect OCR ambiguities if scanned
                ambiguities = ocr_engine.detect_character_ambiguities(doc_data["text_content"])
                amb_notes = f"Detected {len(ambiguities)} potential ambiguities" if ambiguities else None

                doc_record = KnowledgeDocument(
                    title=doc_data["title"],
                    notification_number=doc_data["notification_number"],
                    publication_date=doc_data["publication_date"],
                    effective_date=doc_data["effective_date"],
                    source=doc_data["source"],
                    source_url=doc_data["source_url"],
                    document_type=doc_data["document_type"],
                    page_count=doc_data["page_count"],
                    is_ocr=doc_data["is_ocr"],
                    ocr_confidence=0.84 if doc_data["is_ocr"] else 1.0,
                    ocr_ambiguity_notes=amb_notes,
                    checksum=checksum,
                    processing_status="indexed"
                )
                db.add(doc_record)
                db.commit()
                db.refresh(doc_record)
                doc_id = doc_record.id
            else:
                doc_id = existing_doc.id
                doc_record = existing_doc

            # Generate Chunks
            chunks = document_chunker.split_text_into_chunks(doc_data["text_content"], page_number=1)
            for c_idx, c in enumerate(chunks):
                # Check if chunk exists in DB
                existing_chunk = db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.document_id == doc_id,
                    KnowledgeChunk.chunk_index == c_idx
                ).first()

                if not existing_chunk:
                    chunk_obj = KnowledgeChunk(
                        document_id=doc_id,
                        page_number=c["page_number"],
                        chunk_index=c_idx,
                        section=c.get("section", "General"),
                        chunk_text=c["chunk_text"]
                    )
                    db.add(chunk_obj)
                    db.commit()
                    db.refresh(chunk_obj)
                    chunk_id = chunk_obj.id
                else:
                    chunk_id = existing_chunk.id

                all_chunks_for_index.append({
                    "id": chunk_id,
                    "document_id": doc_id,
                    "doc_title": doc_data["title"],
                    "notification_number": doc_data["notification_number"],
                    "source": doc_data["source"],
                    "page_number": c["page_number"],
                    "section": c.get("section", "General"),
                    "chunk_text": c["chunk_text"],
                    "publication_date": doc_data["publication_date"]
                })

        db.commit()

        # 3. Build Hybrid Vector Index in Memory
        hybrid_vector_store.build_index(all_chunks_for_index)

    except Exception as e:
        db.rollback()
        print(f"Error seeding knowledge base: {e}")
        raise e
    finally:
        if not custom_session:
            db.close()

if __name__ == "__main__":
    seed_database_and_vector_store()
