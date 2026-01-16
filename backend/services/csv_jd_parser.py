from groq import Groq
from pydantic import BaseModel, Field
from typing import List, Optional
import os
from dotenv import load_dotenv
from datetime import datetime
import json  
import pandas as pd  

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class JDSkills(BaseModel):
    required_skills: List[str] = Field(..., description="Comma-separated mandatory skills from Skills/Job Description")
    bonus_skills: List[str] = Field(default_factory=list, description="Good-to-have skills")

class JDData(BaseModel):
    # Core (exact CSV matches)
    sid: str = Field(..., description="Unique SID")
    comments: Optional[str] = Field(default="", description="Comments")
    sub_bu: Optional[str] = Field(default="", description="Sub BU")
    account: Optional[str] = Field(default="", description="Account")
    project: Optional[str] = Field(default="", description="Project")
    sub_practice_name: Optional[str] = Field(default="", description="Sub Practice Name")
    
    # Job details
    competency: Optional[str] = Field(default="", description="Competency")
    designation: str = Field(..., description="Job title/designation")
    job_description: Optional[str] = Field(default="", description="Full job description")
    skills_obj: JDSkills = Field(..., description="Parsed skills structure")
    
    # Billing/Status
    billability: Optional[str] = Field(default="", description="Billability")
    billing_type: Optional[str] = Field(default="", description="Billing Type")
    probability: Optional[float] = Field(default=0.0, description="Probability % as float")
    billed_pct: Optional[str] = Field(default="", description="Billed %")
    project_type: Optional[str] = Field(default="", description="Project Type")
    governance_category: Optional[str] = Field(default="", description="Governance Category")
    
    # Position/Location
    customer_interview: Optional[str] = Field(default="", description="Customer Interview")
    position_type: Optional[str] = Field(default="", description="Position Type")
    location_type: Optional[str] = Field(default="", description="Location Type")
    base_location_country: Optional[str] = Field(default="", description="Base Location Country")
    base_location_city: Optional[str] = Field(default="", description="Base Location City")
    facility: Optional[str] = Field(default="", description="Facility")
    fulfilment_type: Optional[str] = Field(default="", description="Fulfilment Type")
    
    # Status/Dates
    approval_status: Optional[str] = Field(default="", description="Approval Status")
    sid_status: Optional[str] = Field(default="", description="SID Status")
    identified_empid: Optional[str] = Field(default="", description="Identified EmpID")
    identified_empname: Optional[str] = Field(default="", description="Identified EmpName")
    
    original_billable_date: Optional[str] = Field(default="", description="Original Billable Date")
    updated_billable_date: Optional[str] = Field(default="", description="Updated Billable Date")
    billing_end_date: Optional[str] = Field(default="", description="Billing End Date")
    requirement_expiry_date: Optional[str] = Field(default="", description="Requirement Expiry Date")
    resource_required_date: Optional[str] = Field(default="", description="Resource Required Date")
    requirement_initiated_date: Optional[str] = Field(default="", description="Requirement Initiated Date")
    month: Optional[str] = Field(default="", description="Month")
    
    request_initiated_by: Optional[str] = Field(default="", description="Request Initiated By")
    dm: Optional[str] = Field(default="", description="DM")
    bdm: Optional[str] = Field(default="", description="BDM")
    
    # Misc
    remarks: Optional[str] = Field(default="", description="Remarks")
    reason_for_cancel: Optional[str] = Field(default="", description="Reason For Cancel")
    reason_for_lost: Optional[str] = Field(default="", description="Reason For Lost")
    replacement_employee: Optional[str] = Field(default="", description="Replacement Employee")
    urgent: bool = Field(default=False, description="Urgent: true if 'Yes'/urgent text")
    ctc_rate: Optional[str] = Field(default="", description="CTC/Rate")
    customer_reference_id: Optional[str] = Field(default="", description="Customer Reference ID")
    billing_loss_status: Optional[str] = Field(default="", description="Billing Loss Status")
    aging: Optional[float] = Field(default=0.0, description="Aging days as float")
    action_items: Optional[str] = Field(default="", description="Action Items")

def parse_csv_row_to_jd(row_dict: dict) -> dict:
    """Groq LLM: CSV row → full structured JD (47 fields)"""
    text = "\n".join([f"{k}: {v}" for k, v in row_dict.items() if pd.notna(v) and v])
    
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": """
            Extract ALL fields from JD CSV row into exact Pydantic JSON schema.
            - Copy text verbatim for strings (Job Description, Skills, Remarks)
            - Parse Skills column: comma-split → required_skills; good-to-have from description
            - Numerics: Probability/Aging → float; Urgent → true/false
            - Dates → YYYY-MM-DD if parseable, else raw
            - Empty/missing → "" or null/default
            Output ONLY valid JSON matching JDData schema.
            """},
            {"role": "user", "content": f"CSV Row:\n{text}\n\nExtract:"}
        ],
        temperature=0.1,  # Deterministic
        response_format={"type": "json_object"}
    )
    
    jd_json = json.loads(response.choices[0].message.content)
    jd_json["skills"] = jd_json.pop("skills_obj")  # Flatten for DB
    jd_json["parsed"] = {"required_skills": jd_json["skills"]["required_skills"],
                         "bonus_skills": jd_json["skills"]["bonus_skills"]}
    return jd_json
