# VERSION 2.0 - EDUCATIONAL STRUCTURE CLARIFICATION

## Breaking Changes
1. **Conceptual Separation**: Educational Level, Group/Grade, and Field Code are explicitly distinct.
2. **Complete Hierarchy Documented**: All Level→Group→Code mappings now include **allowed academic status** ({0,1} dual vs {1} student-only) in `educational_master.ssot.yaml` and Policy §4.2.
3. **Code Meanings Updated**:
   - Code 7 now exclusively means "Art Experimental Group" (کنکوری).
   - Code 33 now exclusively means "7th Grade" (متوسطه اول).
   - Code 5 now exclusively means "12th Humanities" (کنکوری).
   - Code 41 now exclusively means "5th Grade Elementary" (دبستان).

## Migration Requirements
- Use the status-aware mapping table from Policy §4.2 or `educational_master.ssot.yaml` for all imports/exports.
- Update any legacy mapping that assumed Code 7 = Grade 7 or Code 5 = Grade 5.
- Analytics/reporting must rely on the four-dimensional hierarchy (Level → Group → Code → Allowed Status) and dual-status list {1,3,5,7,8,9,11,12,14,17,18}.

## Validation Rules Added
1. Code 7 → Level = "کنکوری", Group = "هنر"; never valid for "متوسطه اول".
2. Code 33 → Level = "متوسطه اول", Group = "هفتم", `is_experimental_group=false`.
3. Code 41 → Level = "دبستان", Group = "پنجم دبستان".
4. Dual-status enforcement: only codes {1,3,5,7,8,9,11,12,14,17,18} may use {1,0}; all others only {1}.
5. See `educational_validation_rules.yaml` for confusion-matrix coverage of codes 7/33/5/41.

## Usage Examples
- **Correct:** Level="کنکوری", Group="هنر", Code=7
- **Correct:** Level="متوسطه اول", Group="هفتم", Code=33
- **Correct:** Level="دبستان", Group="پنجم دبستان", Code=41
- **Incorrect:** Level="متوسطه اول", Group="هفتم", Code=7 (Code 7 is not Grade 7)
- **Incorrect:** Level="دبستان", Group="پنجم دبستان", Code=5 (Code 5 is 12th Humanities)
- **Incorrect:** Level="کنکوری", Group="دوازدهم ریاضی", Code=24 (کد ۲۴ مربوط به دهم ریاضی در متوسطه دوم است)
