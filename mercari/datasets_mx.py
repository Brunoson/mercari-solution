import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MinMaxScaler, MaxAbsScaler

from mercari.feature_union import FeatureUnionMP, make_union_mp
from mercari.transformers import (
    PandasSelector, FastTokenizer,
    PreprocessDataPJ, PreprocessDataKL, ConcatTexts, PandasToRecords,
    FeaturesEngName, FeaturesEngItemDescription, SparseMatrixOptimize,
    FalseBrands, FeaturesPatterns, ExtractSpecifics, SparsityFilter,
    NumericalVectorizer, ReportShape, FillEmpty, SGDFeatureSelectionV2,
    SanitizeSparseMatrix)


def prepare_vectorizer_1(n_jobs=4):
    tokenizer = FastTokenizer()
    vectorizer = make_pipeline(
        PreprocessDataPJ(n_jobs=n_jobs),
        make_union_mp(

            make_pipeline(
                PandasSelector(columns=['name', 'item_description']),
                ConcatTexts(columns=['name', 'item_description'],
                            use_separators=True),
                PandasSelector(columns=['text_concat']),
                CountVectorizer(ngram_range=(1, 1), binary=True, min_df=5, tokenizer=tokenizer, dtype=np.float32)
            ),

            make_pipeline(PandasSelector(columns=['desc_clean']),
                          CountVectorizer(tokenizer=tokenizer,
                                          binary=True,
                                          min_df=5,
                                          ngram_range=(1, 1),
                                          dtype=np.float32)),

            make_pipeline(PandasSelector(columns=['name_clean']),
                          CountVectorizer(binary=True,
                                          analyzer='char_wb',
                                          min_df=25,
                                          ngram_range=(3, 3),
                                          dtype=np.float32)),

            make_pipeline(PandasSelector(columns=['name_clean']),
                          CountVectorizer(tokenizer=tokenizer,
                                          binary=True,
                                          min_df=5,
                                          ngram_range=(1, 1),
                                          dtype=np.float32),
                          SparseMatrixOptimize()),

            make_pipeline(PandasSelector(columns=['category_name_clean']),
                          CountVectorizer(tokenizer=tokenizer,
                                          binary=True,
                                          min_df=5,
                                          dtype=np.float32)),

            make_pipeline(PandasSelector(columns=['shipping', 'item_condition_id', 'brand_name_clean',
                                                  'cat_1', 'cat_2', 'cat_3', 'no_cat']),
                          PandasToRecords(),
                          DictVectorizer(dtype=np.float32)),

            make_pipeline(PandasSelector(columns=['name_clean'], return_vector=False),
                          FeaturesEngName(),
                          MinMaxScaler()),

            make_pipeline(PandasSelector(columns=['desc_clean'], return_vector=False),
                          FeaturesEngItemDescription(),
                          MinMaxScaler()),

            make_pipeline(PandasSelector(columns=['brand_name', 'item_description']),
                          FalseBrands()),

            make_pipeline(PandasSelector(columns=['item_description'], return_vector=False),
                          FeaturesPatterns(column='item_description')),

            make_pipeline(PandasSelector(columns=['name'], return_vector=False),
                          FeaturesPatterns(column='name')),

            make_pipeline(
                PandasSelector("item_description", return_vector=True),
                ExtractSpecifics(),
                DictVectorizer(),
                SparsityFilter(25),
                MaxAbsScaler()
            ),

            n_jobs=n_jobs
        ),
        SparseMatrixOptimize(),
        SanitizeSparseMatrix(),
        ReportShape()
    )
    return vectorizer


def prepare_vectorizer_2(n_jobs=4):
    TOKEN_PATTERN = (
            r'(?u)('
            r'"|'  # for inches
            r'\&|'  # & (e.g. in H&M)
            r'!+|'  # !
            r'\.\d+\b|'  # .25
            r'\b\d+\/\d+\b|'  # 1/2
            r'\b\d+\.?\d*\%|'  # 100.1%
            r'\b\d+\.?\d*\b|'  # 0.25
            r'[\:\;\%][\)\(]|'  # TODO more smilies
            r'[' + ''.join([
        '•', '❤', '✨', '$', '❌', '♡', '☆', '✔', '⭐',
        '✅', '⚡', '‼', '—', '▪', '❗', '■', '●', '➡',
        '⛔', '♦', '〰', '×', '⚠', '°', '♥', '★', '®', '·', '☺', '–', '➖',
        '✴', '❣', '⚫', '✳', '➕', '™', 'ᴇ', '》', '✖', '▫', '¤',
        '⬆', '⃣', 'ᴀ', '❇', 'ᴏ', '《', '☞', '❄', '»', 'ô', '❎', 'ɴ', '⭕', 'ᴛ',
        '◇', 'ɪ', '½', 'ʀ', '❥', '⚜', '⋆', '⏺', '❕', 'ꕥ', '：', '◆', '✽',
        '…', '☑', '︎', '═', '▶', '⬇', 'ʟ', '！', '✈', '�', '☀', 'ғ',
    ]) + ']|'  # various symbols
         r'\b\w+\b'  # word
         r')')

    # TODO - check gain, maybe remove them?
    REPL_PATTERNS = [
        (r'\b(\d+)([a-z]+)\b', r'\1 \2'),  # 16gb -> 16 gb
        (r'\b([a-z]+)(\d+)\b', r'\1 \2'),  # gtx780 -> gtx 780
        (r'!!+', r'!!'),  # !!!! -> !!
    ]

    max_feat_descr = 100000
    max_feat_name = 100000
    num_brands = 2500

    vectorizer = make_pipeline(
        PreprocessDataKL(num_brands=num_brands, repl_patterns=REPL_PATTERNS),
        FeatureUnionMP([

            ('descr_idf', make_pipeline(
                PandasSelector(columns=['name', 'item_description', 'category_name']),
                ConcatTexts(columns=['name', 'item_description', 'category_name'],
                            use_separators=True),
                PandasSelector(columns=['text_concat']),
                TfidfVectorizer(
                    max_features=max_feat_descr,
                    ngram_range=(1, 2),
                    token_pattern=TOKEN_PATTERN,
                    dtype=np.float32,
                )
            )),

            ('name_idf',
             make_pipeline(
                 PandasSelector(columns=['name', 'brand_name']),
                 ConcatTexts(columns=['name', 'brand_name'],
                             use_separators=True),
                 PandasSelector(columns=['text_concat']),
                 CountVectorizer(
                     max_features=max_feat_name,
                     ngram_range=(1, 2),
                     token_pattern=TOKEN_PATTERN,
                     dtype=np.float32,
                 ))),

            ('num_vect_name', make_pipeline(
                PandasSelector(columns=['name', 'item_description']),
                ConcatTexts(columns=['name', 'item_description'],
                            use_separators=True),
                PandasSelector(columns=['text_concat']),
                NumericalVectorizer(token_pattern=TOKEN_PATTERN,
                                    min_df=5,
                                    stop_words="english",
                                    ngram_range=(1, 1)))),

            ('category_idf',
             make_pipeline(PandasSelector('category_name'),
                           CountVectorizer(dtype=np.float32))),

            ('ohe', make_pipeline(
                PandasSelector(columns=['shipping', 'no_description',
                                        'item_condition_id', 'brand_name',
                                        'category_name_l2', 'category_name']),
                PandasToRecords(),
                DictVectorizer(),
            )),
        ], n_jobs=n_jobs),
        SparseMatrixOptimize(),
        SanitizeSparseMatrix(),
        ReportShape()
    )
    return vectorizer


def prepare_vectorizer_3(n_jobs=4):
    token_pattern = r"(?u)\b\w+\b"
    vectorizer = make_pipeline(
        PreprocessDataPJ(n_jobs=n_jobs),
        FillEmpty(),
        FeatureUnionMP([

            ('tf_idf_1g', make_pipeline(
                PandasSelector(columns=['name_clean', 'brand_name_clean', 'category_name', 'desc_clean']),
                ConcatTexts(columns=['name_clean', 'brand_name_clean', 'category_name', 'desc_clean'],
                            use_separators=True),
                PandasSelector(columns=['text_concat']),
                TfidfVectorizer(ngram_range=(1, 1), binary=True, min_df=5, token_pattern=token_pattern)
            )),

            ('tf_idf_2g', make_pipeline(
                PandasSelector(columns=['name_clean', 'brand_name_clean', 'category_name', 'desc_clean']),
                ConcatTexts(columns=['name_clean', 'brand_name_clean', 'category_name', 'desc_clean'],
                            use_separators=True),
                PandasSelector(columns=['text_concat']),
                TfidfVectorizer(ngram_range=(2, 2), binary=True, min_df=5, token_pattern=token_pattern),
                SGDFeatureSelectionV2(70),
                ReportShape()
            )),

            ('name_chargrams', make_pipeline(
                PandasSelector('name'),
                TfidfVectorizer(ngram_range=(3, 3), analyzer='char', binary=True, min_df=25),
            )),

            ('ohe', make_pipeline(
                PandasSelector(columns=['shipping',
                                        'item_condition_id', 'brand_name',
                                        'cat_1', 'cat_2', 'cat_3', 'no_cat']),
                PandasToRecords(),
                DictVectorizer()
            )),

            ('is_name', make_pipeline(
                PandasSelector("name", return_vector=True),
                ExtractSpecifics(),
                DictVectorizer(),
                SparsityFilter(25),
                MaxAbsScaler()
            ))
        ], n_jobs=n_jobs),
        SparseMatrixOptimize(),
        SanitizeSparseMatrix(),
        ReportShape()
    )
    return vectorizer
