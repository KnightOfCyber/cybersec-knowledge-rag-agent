# cybersec-knowledge-rag-agent
A cybersecurity knowledge assistant using keyword search, semantic search, and retrieval-augmented generation (RAG).

## Current Progress

- Created two cybersecurity knowledge notes.
- Implemented V1 keyword search.
- Retrieved network-security information for a port-scanning question.
- Confirmed that draft notes trigger a trust warning.
- Verified that retrieved answers show their source file.

## Current Limitations

- Only two cybersecurity notes have been added so far.
- Search quality depends on matching keywords.
- Draft information must be verified before use.

- 
## V1 Evaluation

- Test questions: 10
- Correct retrievals: 9
- Keyword retrieval score: 9/10 (90%)

### Failure Analysis

- Question: How do I respond to a leaked token?
- Expected source: `knowledge/cybersecurity/secret-detection.md`
- Result: Retrieval failed.
- Likely cause: The keyword search did not match the question's wording to the note's terminology.
- Planned fix: Evaluate semantic search (V2) on the same test set.

