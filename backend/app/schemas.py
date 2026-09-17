from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class SSOIn(BaseModel):
    provider: str = "saml"
    token: str = ""

class ForgotPasswordIn(BaseModel):
    email: EmailStr

class ResetPasswordIn(BaseModel):
    token: str
    newPassword: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]
    notice: Optional[str] = None


# ---------- Employee ----------
class EmployeeOut(BaseModel):
    id: str
    name: str
    dept: str
    designation: str = ""
    email: str
    phone: str = ""
    location: str = ""
    color: str
    joined: str
    isActive: bool = Field(alias="is_active")
    role: Optional[str] = None
    hasLogin: bool = False

    class Config:
        from_attributes = True
        populate_by_name = True

class EmployeeCreateIn(BaseModel):
    name: str
    email: EmailStr
    dept: str = "General"
    designation: str = ""
    phone: str = ""
    location: str = ""
    color: Optional[str] = None
    createLogin: bool = True
    role: str = "employee"
    password: Optional[str] = None

class EmployeeUpdateIn(BaseModel):
    name: Optional[str] = None
    dept: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    color: Optional[str] = None
    isActive: Optional[bool] = None

class EmployeeCreateOut(BaseModel):
    employee: EmployeeOut
    temporaryPassword: Optional[str] = None


# ---------- Job ----------
class JobIn(BaseModel):
    title: str
    dept: str = "General"
    category: str = "General"
    exp: str = "—"
    location: str = "Bengaluru"
    salary: str = "TBD"
    bonus: int = 50000
    skills: List[str] = []
    status: str = "Open"
    description: str = ""

class JobOut(JobIn):
    id: str
    posted: datetime

    class Config:
        from_attributes = True


# ---------- Referral ----------
class ReferralIn(BaseModel):
    candidateName: str
    phone: str = ""
    email: str = ""
    resumeText: str = ""
    resumeFileUrl: str = ""
    resumeFileName: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    location: str = ""
    expectedSalary: str = ""
    noticePeriod: str = ""
    currentCompany: str = ""
    currentDesignation: str = ""
    totalExperience: str = ""
    relevantExperience: str = ""
    skills: List[str] = []
    education: str = ""
    certifications: List[str] = []
    projects: List[str] = []
    relationship: str = ""
    jobId: str

class ReferralStatusUpdate(BaseModel):
    status: str


class OverrideDecisionIn(BaseModel):
    targetStatus: str
    reason: str = ""


class DeepScreenIn(BaseModel):
    referralId: str


# ---------- Notification ----------
class NotificationOut(BaseModel):
    id: str
    title: str
    message: str
    type: str
    category: str
    isRead: bool = Field(alias="is_read")
    link: str
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True

class NotificationMarkRead(BaseModel):
    ids: List[str] = []


# ---------- Referral Policy ----------
class PolicyUpdateIn(BaseModel):
    content: str


# ---------- Knowledge Base ----------
class KnowledgeArticleIn(BaseModel):
    title: str = Field(min_length=2)
    category: str = "General"
    audience: str = "all"  # all | employee | hr
    content: str = Field(min_length=10)
    tags: List[str] = []


# ---------- Settings ----------
class SettingsOut(BaseModel):
    resumeParsing: bool = Field(alias="resume_parsing")
    duplicateDetection: bool = Field(alias="duplicate_detection")
    fraudDetection: bool = Field(alias="fraud_detection")
    interviewPrediction: bool = Field(alias="interview_prediction")
    chatAssistant: bool = Field(alias="chat_assistant")
    aiProvider: str = Field(alias="ai_provider")
    aiModel: str = Field(alias="ai_model")
    aiApiKey: str = Field(default="", alias="ai_api_key")
    aiTemperature: float = Field(alias="ai_temperature")
    aiMaxTokens: int = Field(alias="ai_max_tokens")
    ocrEnabled: bool = Field(alias="ocr_enabled")
    ocrLanguage: str = Field(alias="ocr_language")

    class Config:
        from_attributes = True
        populate_by_name = True

class SettingsIn(BaseModel):
    resumeParsing: Optional[bool] = None
    duplicateDetection: Optional[bool] = None
    fraudDetection: Optional[bool] = None
    interviewPrediction: Optional[bool] = None
    chatAssistant: Optional[bool] = None
    aiProvider: Optional[str] = None
    aiModel: Optional[str] = None
    aiApiKey: Optional[str] = None
    aiTemperature: Optional[float] = None
    aiMaxTokens: Optional[int] = None
    ocrEnabled: Optional[bool] = None
    ocrLanguage: Optional[str] = None
    smtpHost: Optional[str] = None
    smtpPort: Optional[int] = None
    smtpUser: Optional[str] = None
    smtpPassword: Optional[str] = None
    smtpFrom: Optional[str] = None
    smtpUseTls: Optional[bool] = None
    senderName: Optional[str] = None


class TestSMTPIn(BaseModel):
    smtpHost: Optional[str] = None
    smtpPort: Optional[int] = None
    smtpUser: Optional[str] = None
    smtpPassword: Optional[str] = None
    smtpFrom: Optional[str] = None
    senderName: Optional[str] = None
    smtpUseTls: Optional[bool] = None
    senderName: Optional[str] = None


# ---------- AI ----------
class ResumeTextIn(BaseModel):
    resumeText: str = Field(min_length=20)

class MatchJobIn(BaseModel):
    resumeText: str = Field(min_length=20)
    jobId: str

class CompareIn(BaseModel):
    referralIds: List[str] = Field(min_length=2)

class GenerateEmailIn(BaseModel):
    referralId: str

class GenerateJdIn(BaseModel):
    brief: str

class ChatMessageIn(BaseModel):
    message: str
    history: List[Dict[str, str]] = []

    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("message must not be empty")
        if len(v.strip()) > 4000:
            raise ValueError("message is too long")
        return v.strip()

class ShortlistIn(BaseModel):
    """AI shortlisting input. Provide matchPercent directly, OR resumeText + jobId
    so the backend computes the match first (resume screening Step 1-4)."""
    matchPercent: Optional[float] = None
    resumeText: Optional[str] = None
    jobId: Optional[str] = None


# ---------- Email Center ----------
class EmailSendIn(BaseModel):
    to: List[str]
    cc: List[str] = []
    bcc: List[str] = []
    subject: str
    body: str
    category: str = "manual"  # automated | bulk | ai | manual
    emailType: str = "general"
    referralId: Optional[str] = None
    jobId: Optional[str] = None
    scheduleFor: Optional[str] = None  # ISO datetime — if set, recorded as "scheduled"

class ReferralEmailSendIn(BaseModel):
    to: List[EmailStr] = Field(min_length=1)
    cc: List[EmailStr] = []
    bcc: List[EmailStr] = []
    subject: str = Field(min_length=1, max_length=500)
    body: str = ""
    attachResume: bool = True

class BulkEmailFilterIn(BaseModel):
    status: Optional[str] = None
    jobId: Optional[str] = None
    dept: Optional[str] = None
    matchMin: Optional[float] = None
    matchMax: Optional[float] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    excludeEmailed: bool = False

class BulkEmailSendIn(BulkEmailFilterIn):
    subject: str
    body: str
    emailType: str = "bulk"
    dryRun: bool = False


# ---------- Reports ----------
class ReportFilterIn(BaseModel):
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    dept: Optional[str] = None
    jobId: Optional[str] = None
    status: Optional[str] = None
    employeeId: Optional[str] = None


class ReportExportIn(BaseModel):
    reportType: str = "referral"  # referral | interview | offer | joining | bonus | hiring
    format: str = "xlsx"          # xlsx | pdf
    filters: ReportFilterIn = ReportFilterIn()


# ---------- Audit Log ----------
class AuditLogOut(BaseModel):
    id: str
    user_name: str
    user_role: str
    action: str
    target: str
    target_id: str
    details: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Interview ----------
class InterviewIn(BaseModel):
    referralId: str
    jobId: str = ""
    candidateName: str = ""
    roundName: str = "Technical Round"
    interviewType: str = "Online"
    interviewDate: str = ""
    startTime: str = ""
    endTime: str = ""
    interviewer: str = ""
    meetingLink: str = ""
    location: str = ""
    notes: str = ""

class InterviewUpdate(BaseModel):
    interviewType: Optional[str] = None
    interviewDate: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    interviewer: Optional[str] = None
    meetingLink: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    result: Optional[str] = None
    feedback: Optional[str] = None
    score: Optional[int] = None

class InterviewOut(BaseModel):
    id: str
    referralId: str = Field(alias="referral_id")
    jobId: str = Field(alias="job_id")
    candidateName: str
    roundName: str = Field(alias="round_name")
    interviewType: str = Field(default="Online", alias="interview_type")
    interviewDate: str = Field(alias="interview_date")
    startTime: str = Field(default="", alias="start_time")
    endTime: str = Field(default="", alias="end_time")
    interviewer: str
    meetingLink: str = Field(alias="meeting_link")
    location: str = ""
    notes: str = ""
    status: str
    result: str = ""
    feedback: str
    score: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True

# ---------- Activity Log ----------
class ActivityLogOut(BaseModel):
    id: str
    referralId: str = Field(alias="referral_id")
    action: str
    description: str
    performedBy: str = Field(alias="performed_by")
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True

# ---------- Email Template ----------
class EmailTemplateIn(BaseModel):
    name: str
    templateKey: str
    subject: str = ""
    body: str = ""
    isActive: bool = True

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    isActive: Optional[bool] = None

class EmailTemplateOut(BaseModel):
    id: str
    name: str
    templateKey: str = Field(alias="template_key")
    subject: str
    body: str
    isActive: bool = Field(alias="is_active")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True

# ---------- AI Email Generate ----------
class AiEmailGenerateIn(BaseModel):
    prompt: str
    emailType: str = "general"  # interview_invite | offer | rejection | welcome | reminder | joining | bonus | follow_up | general
    referralId: Optional[str] = None

# ---------- Teams Meeting ----------
class TeamsMeetingIn(BaseModel):
    referralId: str
    interviewId: str = ""
    title: str = ""
    description: str = ""
    startDate: str = ""
    startTime: str = ""
    durationMinutes: int = 30
    attendees: List[str] = []


# ---------- Email Send ----------
class SendEmailIn(BaseModel):
    to: List[str]
    cc: List[str] = []
    bcc: List[str] = []
    subject: str
    body: str
    templateId: Optional[str] = None
    referralId: Optional[str] = None
    interviewId: Optional[str] = ""
    jobId: Optional[str] = ""


# ---------- AI Email Composer ----------
class AiComposeEmailIn(BaseModel):
    prompt: str
    context: str = ""  # interview_invite | reminder | rejection | offer | follow_up | document_request | general
    referralId: Optional[str] = None
    candidateName: str = ""
    jobTitle: str = ""
    companyName: str = "MuraAI"


# ---------- Candidate ----------
class CandidateRegisterIn(BaseModel):
    name: str
    email: str
    password: str
    phone: str = ""

class CandidateApplyIn(BaseModel):
    jobId: str
    resumeText: str = ""
    resumeFileName: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    phone: str = ""
    location: str = ""
    currentCompany: str = ""
    currentDesignation: str = ""
    totalExperience: str = ""
    relevantExperience: str = ""
    skills: List[str] = []
    education: str = ""
    certifications: List[str] = []
    projects: List[str] = []

class CandidateUpdateIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    skills: Optional[str] = None

class GenerateReferralLinkIn(BaseModel):
    candidateEmail: str = ""
    candidateName: str = ""
    jobId: str = ""
