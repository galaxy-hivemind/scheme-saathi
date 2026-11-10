import { apiClient } from './client';
import { DocumentRequirement, UserDocument } from '@/types';
import { MOCK_DOCUMENT_REQUIREMENTS, MOCK_USER_DOCUMENTS } from '../mock/mockData';

let localUserDocs: UserDocument[] = [...MOCK_USER_DOCUMENTS];

export const documentService = {
  async getChecklist(schemeId: string): Promise<DocumentRequirement[]> {
    if (apiClient.isMockMode()) {
      const requirements = MOCK_DOCUMENT_REQUIREMENTS[schemeId] || [
        {
          id: `doc-${schemeId}-generic-aadhaar`,
          scheme_id: schemeId,
          document_type: "aadhaar",
          is_mandatory: true,
          guidance: "Aadhaar Card issued by UIDAI.",
          source_url: "https://uidai.gov.in/",
          last_verified_at: "2026-11-07",
        },
        {
          id: `doc-${schemeId}-generic-income`,
          scheme_id: schemeId,
          document_type: "income_certificate",
          is_mandatory: true,
          guidance: "Income certificate issued by competent authority (Tehsildar/SDM).",
          last_verified_at: "2026-11-07",
        },
      ];
      return Promise.resolve(requirements);
    }
    return apiClient.post<DocumentRequirement[]>('/documents/checklist', { scheme_id: schemeId });
  },

  async getUserDocuments(): Promise<UserDocument[]> {
    if (apiClient.isMockMode()) {
      return Promise.resolve([...localUserDocs]);
    }
    return apiClient.get<UserDocument[]>('/documents');
  },

  async uploadDocument(documentType: string, file: File): Promise<UserDocument> {
    if (apiClient.isMockMode()) {
      const newDoc: UserDocument = {
        id: `user-doc-${Date.now()}`,
        user_id: "user-101-uuid",
        document_type: documentType,
        upload_status: "uploaded",
        ocr_status: "completed",
        review_status: "pending_review",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      localUserDocs.push(newDoc);
      return Promise.resolve(newDoc);
    }

    const formData = new FormData();
    formData.append('document_type', documentType);
    formData.append('file', file);
    return apiClient.upload<UserDocument>('/documents/upload', formData);
  },

  async getGuidance(documentId: string): Promise<{ guidance: string }> {
    if (apiClient.isMockMode()) {
      return Promise.resolve({
        guidance: "Apply online via the State Edistrict portal or visit your nearest Common Service Centre (CSC) with your ration card and identity proof.",
      });
    }
    return apiClient.get<{ guidance: string }>(`/documents/${documentId}/guidance`);
  },
};
