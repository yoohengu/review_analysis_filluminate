USE review_analysis;

-- DROP TABLE IF EXISTS survey_001, survey_002, survey_003;
-- DROP TABLE IF EXISTS reviews_001, reviews_002, reviews_003;
-- DROP TABLE IF EXISTS products_001, products_002, products_003;

CREATE TABLE products_001 (
    goodsNo     BIGINT PRIMARY KEY,
    플랫폼        VARCHAR(50),
    카테고리       VARCHAR(100),
    브랜드        VARCHAR(100),
    상품명        VARCHAR(500),
    정가         BIGINT,
    판매가        BIGINT,
    할인율        BIGINT,
    조회수        BIGINT,
    누적판매수      BIGINT,
    리뷰수        BIGINT,
    리뷰점수       BIGINT
);

CREATE TABLE products_002 (
    goodsNo     BIGINT PRIMARY KEY,
    플랫폼        VARCHAR(50),
    카테고리       VARCHAR(100),
    브랜드        VARCHAR(100),
    상품명        VARCHAR(500),
    정가         BIGINT,
    판매가        BIGINT,
    할인율        BIGINT,
    조회수        BIGINT,
    누적판매수      BIGINT,
    리뷰수        BIGINT,
    리뷰점수       BIGINT
);

CREATE TABLE products_003 (
    goodsNo     BIGINT PRIMARY KEY,
    플랫폼        VARCHAR(50),
    카테고리       VARCHAR(100),
    브랜드        VARCHAR(100),
    상품명        VARCHAR(500),
    정가         BIGINT,
    판매가        BIGINT,
    할인율        BIGINT,
    조회수        BIGINT,
    누적판매수      BIGINT,
    리뷰수        BIGINT,
    리뷰점수       BIGINT
);

CREATE TABLE reviews_001 (
    리뷰번호    BIGINT PRIMARY KEY,
    goodsNo  BIGINT,
    작성자     VARCHAR(100),
    리뷰내용    TEXT,
    평점       BIGINT,
    체험단     VARCHAR(10),
    구매옵션    VARCHAR(200),
    키        BIGINT,
    몸무게     BIGINT,
    성별       VARCHAR(10),
    작성일     VARCHAR(50),
    만족도     VARCHAR(200),
    사진유무    VARCHAR(10),
    도움돼요    BIGINT,
    FOREIGN KEY (goodsNo) REFERENCES products_001(goodsNo)
);

CREATE TABLE reviews_002 (
    리뷰번호    BIGINT PRIMARY KEY,
    goodsNo  BIGINT,
    작성자     VARCHAR(100),
    리뷰내용    TEXT,
    평점       BIGINT,
    체험단     VARCHAR(10),
    구매옵션    VARCHAR(200),
    키        BIGINT,
    몸무게     BIGINT,
    성별       VARCHAR(10),
    작성일     VARCHAR(50),
    만족도     VARCHAR(200),
    사진유무    VARCHAR(10),
    도움돼요    BIGINT,
    FOREIGN KEY (goodsNo) REFERENCES products_002(goodsNo)
);

CREATE TABLE reviews_003 (
    리뷰번호    BIGINT PRIMARY KEY,
    goodsNo  BIGINT,
    작성자     VARCHAR(100),
    리뷰내용    TEXT,
    평점       BIGINT,
    체험단     VARCHAR(10),
    구매옵션    VARCHAR(200),
    키        BIGINT,
    몸무게     BIGINT,
    성별       VARCHAR(10),
    작성일     VARCHAR(50),
    만족도     VARCHAR(200),
    사진유무    VARCHAR(10),
    도움돼요    BIGINT,
    FOREIGN KEY (goodsNo) REFERENCES products_003(goodsNo)
);

CREATE TABLE survey_001 (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    goodsNo  BIGINT,
    항목      VARCHAR(200),
    답변      VARCHAR(200),
    비율      BIGINT,
    응답수    BIGINT,
    FOREIGN KEY (goodsNo) REFERENCES products_001(goodsNo)
);

CREATE TABLE survey_002 (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    goodsNo  BIGINT,
    항목      VARCHAR(200),
    답변      VARCHAR(200),
    비율      BIGINT,
    응답수    BIGINT,
    FOREIGN KEY (goodsNo) REFERENCES products_002(goodsNo)
);

CREATE TABLE survey_003 (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    goodsNo  BIGINT,
    항목      VARCHAR(200),
    답변      VARCHAR(200),
    비율      BIGINT,
    응답수    BIGINT,
    FOREIGN KEY (goodsNo) REFERENCES products_003(goodsNo)
);








