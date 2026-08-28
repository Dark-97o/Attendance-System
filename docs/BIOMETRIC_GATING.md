# Biometric Dual-Factor Gating Architecture

## Slot Assignment & Collision Prevention
When registering or updating a teacher with a hardware fingerprint slot, the database automatically frees the slot from any existing assignment to avoid UNIQUE constraint violations:

```sql
UPDATE teachers SET fingerprint_id = NULL WHERE fingerprint_id = ? AND teacher_id != ?;
```

## SFace Multi-Modal Matching
The system evaluates facial vectors against enrolled student and teacher embeddings using in-memory cosine dot-product indexing.
