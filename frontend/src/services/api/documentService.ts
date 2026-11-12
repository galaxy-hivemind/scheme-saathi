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
          document_type: 'aadhaar',
          is_mandatory: true,
          guidance: 'Aadhaar Card issued by UIDAI.',
          source_url: 'https://uidai.gov.in/',
          last_verified_at: '2026-11-07',
        },
        {
          id: `doc-${schemeId}-generic-income`,
          scheme_id: schemeId,
          document_type: 'income_certificate',
          is_mandatory: true,
          guidance: 'Income certificate issued by competent authority (Tehsildar/SDM).',
          last_verified_at: '2026-11-07',
        },
      ];
      return Promise.resolve(requirements);
    }
    return apiClient.post<DocumentRequirement[]>('/documents/checklist', { scheme_id: schemeId });
  },

  async getCategories(lang: string = 'en'): Promise<Array<{ value: string; label: string }>> {
    if (apiClient.isMockMode()) {
      return Promise.resolve([
        { value: 'aadhaar_card', label: 'Aadhaar Card' },
        { value: 'bank_passbook', label: 'Bank Passbook' },
        { value: 'income_certificate', label: 'Income Certificate' },
        { value: 'land_records', label: 'Land Ownership Records' },
        { value: 'land_possession', label: 'Homestead Land / Allotment Proof' },
        { value: 'job_card', label: 'MGNREGA Job Card' },
      ]);
    }
    return apiClient.get<Array<{ value: string; label: string }>>('/documents/categories', { lang });
  },

  async getUserDocuments(): Promise<UserDocument[]> {
    if (apiClient.isMockMode()) {
      return Promise.resolve([...localUserDocs]);
    }
    return apiClient.get<UserDocument[]>('/documents');
  },

  async getDocumentDetails(docId: string): Promise<UserDocument> {
    if (apiClient.isMockMode()) {
      const doc = localUserDocs.find((d) => d.id === docId);
      if (!doc) throw { code: 'NOT_FOUND', message: 'Document not found' };
      return Promise.resolve(doc);
    }
    return apiClient.get<UserDocument>(`/documents/${docId}`);
  },

  async fetchDocumentPreviewUrl(docId: string): Promise<string> {
    const blob = await apiClient.fetchBlob(`/documents/${docId}/file`);
    return URL.createObjectURL(blob);
  },

  async uploadDocument(documentType: string, file: File): Promise<UserDocument> {
    if (apiClient.isMockMode()) {
      const now = new Date().toISOString();
      const newDoc: UserDocument = {
        id: `user-doc-${Date.now()}`,
        user_id: 'user-101-uuid',
        document_type: documentType,
        file_name: file.name,
        content_type: file.type,
        size_bytes: file.size,
        upload_status: 'uploaded',
        ocr_status: 'limited',
        lifecycle_status: 'awaiting_citizen_review',
        verification_status: 'awaiting_citizen_review',
        review_status: 'pending_review',
        extracted_fields: {},
        reviewed_fields: {},
        citizen_confirmed_accurate: false,
        created_at: now,
        updated_at: now,
      };
      localUserDocs.unshift(newDoc);
      return Promise.resolve(newDoc);
    }

    const formData = new FormData();
    formData.append('document_type', documentType);
    formData.append('file', file);
    return apiClient.upload<UserDocument>('/documents/upload', formData);
  },

  async reviewDocument(
    docId: string,
    reviewedFields: Record<string, unknown>,
    confirmedAccurate: boolean = true
  ): Promise<UserDocument> {
    if (apiClient.isMockMode()) {
      const idx = localUserDocs.findIndex((d) => d.id === docId);
      if (idx === -1) throw { code: 'NOT_FOUND', message: 'Document not found' };
      localUserDocs[idx] = {
        ...localUserDocs[idx],
        reviewed_fields: reviewedFields,
        citizen_confirmed_accurate: confirmedAccurate,
        lifecycle_status: confirmedAccurate ? 'reviewed' : 'awaiting_citizen_review',
        verification_status: confirmedAccurate ? 'reviewed' : 'awaiting_citizen_review',
        review_status: confirmedAccurate ? 'reviewed' : 'pending_review',
        updated_at: new Date().toISOString(),
      };
      return Promise.resolve(localUserDocs[idx]);
    }
    return apiClient.post<UserDocument>(`/documents/${docId}/review`, {
      reviewed_fields: reviewedFields,
      confirmed_accurate: confirmedAccurate,
    });
  },

  async verifyDocument(
    docId: string,
    options?: { reject?: boolean; rejection_reason?: string }
  ): Promise<UserDocument> {
    if (apiClient.isMockMode()) {
      const idx = localUserDocs.findIndex((d) => d.id === docId);
      if (idx === -1) throw { code: 'NOT_FOUND', message: 'Document not found' };
      const status = options?.reject ? 'rejected' : 'verified';
      localUserDocs[idx] = {
        ...localUserDocs[idx],
        lifecycle_status: status,
        verification_status: status,
        review_status: status,
        rejection_reason: options?.reject ? options.rejection_reason || 'Rejected' : null,
        updated_at: new Date().toISOString(),
      };
      return Promise.resolve(localUserDocs[idx]);
    }
    return apiClient.post<UserDocument>(`/documents/${docId}/verify`, options || {});
  },

  async deleteDocument(docId: string): Promise<{ deleted: boolean; id: string }> {
    if (apiClient.isMockMode()) {
      localUserDocs = localUserDocs.filter((d) => d.id !== docId);
      return Promise.resolve({ deleted: true, id: docId });
    }
    return apiClient.delete<{ deleted: boolean; id: string }>(`/documents/${docId}`);
  },

  async getGuidance(documentId: string): Promise<{ guidance: string }> {
    if (apiClient.isMockMode()) {
      return Promise.resolve({
        guidance:
          'Apply online via the State Edistrict portal or visit your nearest Common Service Centre (CSC) with your ration card and identity proof.',
      });
    }
    return apiClient.get<{ guidance: string }>(`/documents/${documentId}/guidance`);
  },
};
