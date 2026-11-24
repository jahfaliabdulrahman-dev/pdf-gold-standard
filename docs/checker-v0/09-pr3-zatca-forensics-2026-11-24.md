# PR-3 — تحليل إشارات ZATCA على 16 فاتورة PDF/A-3

**المجموعة:** 16 ملفًا من `zatca-einvoicing-sdk-Java-238-R3.4.8/Data/Samples/PDF-A3` (مصدر رسمي).
**القرّاء:** pdfium، PDFKit، MuPDF، poppler، pdfminer — نسخ فعلية من كل قارئ؛ لا OCR ولا حكم على الرسم.
**الملاحظة:** `pf_file` = أشكال العرض في طبقة الملف، و`pf_reader` = أشكال العرض في نسخة القارئ.

| # | الملف | pf_file | share | pdfium pf | pdfkit pf | mupdf pf | poppler pf | pdfminer pf | قرّاء الترتيب البصري |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Advance Payment adjustments with foreign currency invoice.pdf | 839 | 0.8106 | 0 | 839 | 839 | 839 | 839 | pdfminer |
| 2 | Advance Payment adjustments with rate change scenarios.pdf | 812 | 0.8096 | 0 | 812 | 812 | 812 | 812 | pdfminer |
| 3 | Advance Payment adjustments.pdf | 812 | 0.8096 | 0 | 812 | 812 | 812 | 812 | pdfminer |
| 4 | Credit Note of a Simplified Tax Invoice.pdf | 481 | 0.7671 | 0 | 481 | 481 | 481 | 481 | pdfminer |
| 5 | Exempt Tax Invoice.pdf | 683 | 0.7988 | 0 | 683 | 683 | 683 | 683 | pdfminer |
| 6 | Export invoice.pdf | 692 | 0.8019 | 0 | 692 | 692 | 692 | 692 | pdfminer |
| 7 | Nominal supply invoice.pdf | 386 | 0.7959 | 0 | 386 | 386 | 386 | 386 | pdfminer |
| 8 | Out of Scope Standard Tax Invoice.pdf | 694 | 0.7886 | 0 | 694 | 694 | 694 | 694 | pdfminer |
| 9 | Self-billing invoice.pdf | 648 | 0.7931 | 0 | 4 | 0 | 0 | 648 | pdfium,pdfminer |
| 10 | Simplified Tax Invoice with Zero Rated Item.pdf | 451 | 0.7898 | 0 | 451 | 451 | 451 | 451 | pdfminer |
| 11 | Simplified_Invoice.pdf | 445 | 0.7989 | 0 | 3 | 0 | 0 | 445 | pdfium,pdfminer |
| 12 | Standard_Credit_Note.pdf | 719 | 0.7765 | 0 | 9 | 0 | 0 | 719 | pdfium,pdfminer |
| 13 | Standard_Debit_Note.pdf | 723 | 0.7808 | 0 | 9 | 0 | 0 | 723 | pdfium,pdfminer |
| 14 | Standard_Invoice.pdf | 693 | 0.7947 | 0 | 4 | 0 | 0 | 693 | pdfium,pdfminer |
| 15 | Summary Invoice.pdf | 643 | 0.789 | 0 | 643 | 643 | 643 | 643 | pdfminer |
| 16 | Third party billing.pdf | 621 | 0.7911 | 0 | 621 | 621 | 621 | 621 | pdfminer |

## نسخ فعلي (أول سطر عربي من كل قارئ)

### 1. Advance Payment adjustments with foreign currency invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice` |
| mupdf | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| poppler | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 2. Advance Payment adjustments with rate change scenarios.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice` |
| mupdf | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| poppler | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 3. Advance Payment adjustments.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice` |
| mupdf | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| poppler | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 4. Credit Note of a Simplified Tax Invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Credit Note دائن إشعار` |
| pdfkit | `إﺷﻌﺎر داﺋﻦ Credit Note` |
| mupdf | `Credit Note إﺷﻌﺎر داﺋﻦ` |
| poppler | `Credit Note إﺷﻌﺎر داﺋﻦ` |
| pdfminer | `Credit Note ﻦﺋاد رﺎﻌﺷإ` |

### 5. Exempt Tax Invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice` |
| mupdf | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| poppler | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 6. Export invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice` |
| mupdf | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| poppler | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 7. Nominal supply invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Simplified Tax invoice مبسطة ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ Simplified Tax invoice` |
| mupdf | `Simplified Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ` |
| poppler | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ Simplified Tax invoice` |
| pdfminer | `Simplified Tax invoice ﺔﻄﺴﺒﻣ ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 8. Out of Scope Standard Tax Invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice` |
| mupdf | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| poppler | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 9. Self-billing invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Self Billed tax invoice ةيبيرض ةيتاذ فاتورة` |
| pdfkit | `فاتورة ذاتية ضريبية Self Billed tax invoice` |
| mupdf | `Self Billed tax invoice فاتورة ذاتية ضريبية` |
| poppler | `Self Billed tax invoice فاتورة ذاتية ضريبية` |
| pdfminer | `Self Billed tax invoice ﺔﻴﺒﻳﺮﺿ ﺔﻴﺗاذ ةرﻮﺗﺎﻓ` |

### 10. Simplified Tax Invoice with Zero Rated Item.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Simplified Tax invoice مبسطة ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ Simplified Tax invoice` |
| mupdf | `Simplified Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ` |
| poppler | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ Simplified Tax invoice` |
| pdfminer | `Simplified Tax invoice ﺔﻄﺴﺒﻣ ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 11. Simplified_Invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Simplified Tax invoice ةطسبم ةيبيرض فاتورة` |
| pdfkit | `فاتورة ضريبية مبسطة Simplified Tax invoice` |
| mupdf | `Simplified Tax invoice فاتورة ضريبية مبسطة` |
| poppler | `فاتورة ضريبية مبسطة Simplified Tax invoice` |
| pdfminer | `Simplified Tax invoice ﺔﻄﺴﺒﻣ ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 12. Standard_Credit_Note.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Credit Note نئاد إشعار` |
| pdfkit | `إشعار دائن Credit Note` |
| mupdf | `Credit Note إشعار دائن` |
| poppler | `Credit Note إشعار دائن` |
| pdfminer | `Credit Note ﻦﺋاد رﺎﻌﺷإ` |

### 13. Standard_Debit_Note.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Debit Note نيدم إشعار` |
| pdfkit | `إشعار مدين Debit Note` |
| mupdf | `Debit Note إشعار مدين` |
| poppler | `Debit Note إشعار مدين` |
| pdfminer | `Debit Note ﻦﻳﺪﻣ رﺎﻌﺷإ` |

### 14. Standard_Invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ةيبيرض فاتورة` |
| pdfkit | `فاتورة ضريبية Tax invoice` |
| mupdf | `Tax invoice فاتورة ضريبية` |
| poppler | `Tax invoice فاتورة ضريبية` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 15. Summary Invoice.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice` |
| mupdf | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| poppler | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

### 16. Third party billing.pdf
| القارئ | exemplar |
|---|---|
| pdfium | `Tax invoice ضريبية فاتورة` |
| pdfkit | `ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice` |
| mupdf | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| poppler | `Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ` |
| pdfminer | `Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ` |

## الحكم لكل إشارة

- **presentation-forms:** عيب حقيقي في طبقة الملف على 16/16 (386–839 شكلًا، share 0.7671–0.8106). PDFium يطبّعها إلى حروف أساس (0 شكل)؛ PDFKit/MuPDF/poppler ينسخونها كاملة في 11/16، وينسخون جزءًا/صفرًا في 5/16؛ PDFMiner ينسخها كاملة في 16/16. لذا النسخ من 4 عائلات قرّاء يعطي أشكال عرض، وليس حروفًا عربية أساسية.
- **visual-order:** ليس إشارة ملف على أي من الـ16: PDFMiner معكوس 16/16، وPDFium معكوس 5/16، والبقية منطقيون؛ لا أغلبية 3/5. إشارة على مستوى القارئ، لا عيب ملف (ولا إيجابية كاذبة: سلوك قارئ مقاس).
- **tounicode-gaps:** غائبة على 16/16: `missing_unicode=0`، `notdef=0`، `pua=0`. ليست سبب «عالٍ» ولا إشارة كاذبة؛ لا شيء لتُظهره.
- **الحكم:** الفواتير معطوبة فعليًا للنسخ من معظم القرّاء، والمولّد الرسمي للـSDK هو مصدر طبقة أشكال العرض. PDFium وحده يستعيد الحروف الأساس؛ النسخ من متصفح Chrome قد يبدو سليمًا، والنسخ من Preview/MuPDF/poppler/pdfminer لا.

## ما لم يُثبت

- هل يكتب الـSDK أشكال العرض مباشرة أم معالج لاحق؟ يحتاج قراءة شيفرة/سلسلة توليد SDK؛ هذه القياسات تثبت الملف لا المنتِج.
- سلوك Acrobat/Reader وOffice لم يُقس؛ القائمة خمسة قرّاء فقط.
- هل الشكل المرئي مطابق للمصدر؟ لم نُجرِ مقارنة بصرية/OCR؛ الفحص عن النسخ لا الرسم.
- نسبة 5/16 التي يطبّع فيها PDFKit/MuPDF/poppler تحتاج تسمية الخط/الخريطة المسؤولة؛ هنا فقط العدّ.
