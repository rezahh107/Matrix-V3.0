# EDUCATIONAL CODES DATA DICTIONARY

## Field: `educational_level`
- **Type**: Categorical String
- **Allowed Values**: ["کنکوری", "متوسطه دوم", "متوسطه اول", "دبستان", "هنرستان"]
- **Description**: Broad academic stage

## Field: `experimental_group`
- **Type**: Categorical String
- **Examples**: "دوازدهم ریاضی", "هفتم", "پنجم دبستان", "هنر"
- **Description**: Specific study group or grade level

## Field: `field_code`
- **Type**: Integer
- **Range**: 1-89 (based on current mappings)
- **Critical Notes**:
  - Code 7 ≠ Grade 7 (Code 7 = Art group)
  - Grade 7 = Code 33
  - Code 5 ≠ Grade 5 (Code 5 = 12th Humanities)
  - Grade 5 = Code 41

## Field: `allowed_academic_status`
- **Type**: Set of Integers
- **Allowed Values**:
  - `{0,1}`: Student or Graduate (دانش آموز یا فارغ التحصیل)
  - `{1}`: Student Only (فقط دانش آموز)
- **Business Rule**: Determines if graduates can enroll
- **Dual-Status Groups**: 11 codes (1,3,5,7,8,9,11,12,14,17,18)
- **Student-Only Groups**: 22 codes (همهٔ کدهای دیگر در جدول مرجع با وضعیت {1})

## Field: `student_status`
- **Type**: Integer
- **Allowed Values**: 0 = فارغ التحصیل, 1 = دانش آموز
- **Validation**:
  - If `allowed_academic_status` = `{1}`, then `student_status` MUST be 1
  - If `allowed_academic_status` = `{0,1}`, then `student_status` can be 0 or 1

## Complete Educational Mapping (status-aware)
| مقطع تحصیلی | گروه آزمایشی/پایه | کد رشته | Dual-status | وضعیت تحصیلی مجاز |
| --- | --- | --- | --- | --- |
| کنکوری | دوازدهم ریاضی | 1 | ✔ | {0,1} |
| کنکوری | دوازدهم تجربی | 3 | ✔ | {0,1} |
| کنکوری | دوازدهم انسانی | 5 | ✔ | {0,1} |
| کنکوری | هنر | 7 | ✔ (کد ۷ ≠ پایه هفتم) | {0,1} |
| کنکوری | دوازدهم علوم و معارف اسلامی | 8 | ✔ | {0,1} |
| کنکوری | منحصرا زبان | 9 | ✔ | {0,1} |
| متوسطه دوم | دهم ریاضی | 24 | ✖ | {1} |
| متوسطه دوم | دهم تجربی | 25 | ✖ | {1} |
| متوسطه دوم | دهم انسانی | 26 | ✖ | {1} |
| متوسطه دوم | دهم علوم و معارف اسلامی | 30 | ✖ | {1} |
| متوسطه دوم | یازدهم ریاضی | 21 | ✖ | {1} |
| متوسطه دوم | یازدهم تجربی | 22 | ✖ | {1} |
| متوسطه دوم | یازدهم علوم انسانی | 23 | ✖ | {1} |
| متوسطه دوم | یازدهم علوم و معارف اسلامی | 29 | ✖ | {1} |
| متوسطه اول | نهم | 27 | ✖ | {1} |
| متوسطه اول | هشتم | 31 | ✖ | {1} |
| متوسطه اول | هفتم | 33 | ✖ (پایه هفتم واقعی) | {1} |
| دبستان | دوم دبستان | 46 | ✖ | {1} |
| دبستان | سوم دبستان | 45 | ✖ | {1} |
| دبستان | چهارم دبستان | 43 | ✖ | {1} |
| دبستان | پنجم دبستان | 41 | ✖ (پایه پنجم واقعی) | {1} |
| دبستان | ششم دبستان | 35 | ✖ | {1} |
| هنرستان | دوازدهم الکتروتکنیک | 11 | ✔ | {0,1} |
| هنرستان | دوازدهم شبکه و نرم‌افزار رایانه | 12 | ✔ | {0,1} |
| هنرستان | دوازدهم تربیت بدنی | 14 | ✔ | {0,1} |
| هنرستان | دوازدهم حسابداری | 17 | ✔ | {0,1} |
| هنرستان | دوازدهم مکانیک خودرو | 18 | ✔ | {0,1} |
| هنرستان | یازدهم الکتروتکنیک | 53 | ✖ | {1} |
| هنرستان | یازدهم شبکه و نرم افزار | 55 | ✖ | {1} |
| هنرستان | یازدهم تربیت بدنی | 66 | ✖ | {1} |
| هنرستان | یازدهم حسابداری | 69 | ✖ | {1} |
| هنرستان | دهم شبکه و نرم‌افزار رایانه | 83 | ✖ | {1} |
| هنرستان | دهم حسابداری | 89 | ✖ | {1} |

### Hierarchy Stats
- Total mappings: 33
- Dual-status codes: {1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18} → {1, 0}
- Student-only codes: {21, 22, 23, 24, 25, 26, 27, 29, 30, 31, 33, 35, 41, 43, 45, 46, 53, 55, 66, 69, 83, 89} → {1}
- Experimental groups (کنکوری): 6 | Grade groups (پایه‌ها و هنرستان): 27
