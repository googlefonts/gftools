import pytest
from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontFeatures.glyphs import GlyphCombinator
import os


TEST_DATA = os.path.join("data", "test")


@pytest.fixture
def ttFont():
    fontpath = os.path.join(TEST_DATA, "Montserrat-Regular.ttf")
    font = TTFont(fontpath)
    del font['GSUB']
    return font


def test_SingleSubstitution(ttFont):
    fea = """
    feature liga {
        sub A by a.sc;
        sub B by b.sc;
    } liga;

    """
    addOpenTypeFeaturesFromString(ttFont, fea)
    # TODO: don't keep saving!
    ttFont.save(ttFont.reader.file.name)
    i = GlyphCombinator(ttFont)
    i.get_combinations()
    assert i.glyphs['a.sc'] == "A"
    assert i.glyphs['b.sc'] == "B"
    print()


def test_LigSub(ttFont):
    fea = """
    feature liga {
        sub f i by fi.ss01;
    } liga;
    """
    addOpenTypeFeaturesFromString(ttFont, fea)
    ttFont.save(ttFont.reader.file.name)
    i = GlyphCombinator(ttFont)
    i.get_combinations()
    assert i.glyphs['fi.ss01'] == "fi"
    print()


def test_context1(ttFont):
    fea = """
    feature liga {
        sub [A B C] Adieresis' by Adieresis.alt;
    } liga;
    """
    addOpenTypeFeaturesFromString(ttFont, fea)
    ttFont.save(ttFont.reader.file.name)
    i = GlyphCombinator(ttFont)
    i.get_combinations()
    assert i.glyphs["A-Adieresis.alt"] == "AÄ"
    assert i.glyphs["B-Adieresis.alt"] == "BÄ"
    assert i.glyphs["C-Adieresis.alt"] == "CÄ"


def test_context2(ttFont):
    # check if we can get replacements from lookups
    fea = """
    lookup foo {
        sub Adieresis by Adieresis.alt;
    } foo;
    feature liga {
        sub [A B C] Adieresis' lookup foo;
    } liga;
    """
    addOpenTypeFeaturesFromString(ttFont, fea)
    ttFont.save(ttFont.reader.file.name)
    i = GlyphCombinator(ttFont)
    i.get_combinations()
    assert i.glyphs["A-Adieresis.alt"] == "AÄ"
    assert i.glyphs["B-Adieresis.alt"] == "BÄ"
    assert i.glyphs["C-Adieresis.alt"] == "CÄ"


def test_context3(ttFont):
    # check if we can get the appropriate replacement from a lookups which contains multiple rules
    fea = """
    lookup foo {
        sub Adieresis by Adieresis.alt;
        sub Udieresis by Udieresis.alt;
    } foo;
    feature liga {
        sub A [Adieresis Udieresis]' lookup foo;
        sub B [Adieresis Udieresis]' lookup foo;
    } liga;
    """
    addOpenTypeFeaturesFromString(ttFont, fea)
    ttFont.save(ttFont.reader.file.name)
    i = GlyphCombinator(ttFont)
    i.get_combinations()
    assert i.glyphs["A-Adieresis.alt"] == "AÄ"
    assert i.glyphs["A-Udieresis.alt"] == "AÜ"
    assert i.glyphs["B-Adieresis.alt"] == "BÄ"
    assert i.glyphs["B-Udieresis.alt"] == "BÜ"


def test_context4(ttFont):
    # check multiple lookups in a rule
    fea = """
    lookup foo {
        sub Adieresis by Adieresis.alt;
        sub Udieresis by Udieresis.alt;
    } foo;

    lookup foo2 {
        sub a by a.sc;
        sub b by b.sc;
    } foo2;

    feature liga {
        sub A [Adieresis Udieresis]' lookup foo [a b]' lookup foo2;
    } liga;
    """
    addOpenTypeFeaturesFromString(ttFont, fea)
    ttFont.save(ttFont.reader.file.name)
    i = GlyphCombinator(ttFont)
    i.get_combinations()
    assert i.glyphs['A-Adieresis.alt-a.sc'] == 'AÄa'
    assert i.glyphs['A-Adieresis.alt-b.sc'] == 'AÄb'
    assert i.glyphs['A-Udieresis.alt-a.sc'] == 'AÜa'
    assert i.glyphs['A-Udieresis.alt-b.sc'] == 'AÜb'


# Let's test out Poppins since this is pretty hardcore
@pytest.fixture
def poppins_ttFont():
    fontpath = os.path.join(TEST_DATA, "Poppins-Regular.ttf")
    font = TTFont(fontpath)
    return font

def test_poppins_conjunct(poppins_ttFont):
    # test dvSH_KxA can be assembled
    fea = """
    languagesystem DFLT dflt;
    languagesystem dev2 dflt;
    languagesystem deva dflt;

    lookup LigatureSubstitution1 {
        sub dvKA dvNukta by dvKxA;
    } LigatureSubstitution1;

    lookup LigatureSubstitution3 {
        sub dvSHA dvVirama by dvSH;
    } LigatureSubstitution3;

    lookup LigatureSubstitution4 {
        sub dvSH dvKxA by dvSH_KxA;
    } LigatureSubstitution4;

    feature nukt {
        lookup LigatureSubstitution1;
    } nukt;

    feature pres {
        lookup LigatureSubstitution4;
    } pres;
    
    feature half {
        lookup LigatureSubstitution3;
    } half;

    """
    addOpenTypeFeaturesFromString(poppins_ttFont, fea)
    poppins_ttFont.save(poppins_ttFont.reader.file.name)
    i = GlyphCombinator(poppins_ttFont)
    i.get_combinations()
    assert i.glyphs['dvKxA'] == "क़"
    assert i.glyphs['dvSH'] == "श्"
    assert i.glyphs['dvSH_KxA'] == "श्क़"


def test_poppins_matrai(poppins_ttFont):
    fea = """
    languagesystem DFLT dflt;
    languagesystem dev2 dflt;
    languagesystem deva dflt;
    @class1 = [dvGA dvKA];
    
    lookup matrai3 {
        sub dvmI by dvmI.a03;
    } matrai3;

    lookup matrai {
        sub dvmI' lookup matrai3 @class1;
    } matrai;

    feature pres {
        lookup matrai;        
    } pres;
    """
    addOpenTypeFeaturesFromString(poppins_ttFont, fea)
    poppins_ttFont.save(poppins_ttFont.reader.file.name)
    i = GlyphCombinator(poppins_ttFont)
    i.get_combinations()
    assert i.glyphs["dvmI.a03-dvKA"] == 'कि'
    assert i.glyphs["dvmI.a03-dvGA"] == 'गि'


def test_poppins_reph(poppins_ttFont):
    # test we can get reph, ra conjuncts, dmatraI + reph combos.
    fea = """
    languagesystem DFLT dflt;
    languagesystem dev2 dflt;
    languagesystem deva dflt;
    @class1 = [dvGA dvKA dvK_RA];
    @class25 = [dvmI dvmI.a03];
    @class26 = [dvKA dvK_RA];
    
    lookup LigatureSubstitution4 {
        # Original source: 3 
        sub dvRA dvVirama by dvReph;
    } LigatureSubstitution4;

    lookup LigatureSubstitution8 {
        sub dvKA dvVirama dvRA by dvK_RA;
    } LigatureSubstitution8;

    lookup matrai3 {
        sub dvmI by dvmI.a03;
    } matrai3;

    lookup matrai {
        sub dvmI' lookup matrai3 @class1;
    } matrai;

    # reph combiners
    lookup SingleSubstitution52 {
        ;
        # Original source: 51 
        sub [dvmII dvRA dvAnusvara dvReph dvReph_Anusvara dvmII_Anusvara dvmII_Reph dvmII_Reph_Anusvara] by [dvmII.aLong dvvLL dvAnusvara.amI dvReph.amI dvReph_Anusvara.amI dvmII_Anusvara.aLong dvmII_Reph.aLong dvmII_Reph_Anusvara.aLong];
    } SingleSubstitution52;

    lookup ChainedContextualGSUB17 {
        ;
        # Original source: 16 
        sub @class25 @class26 [dvAnusvara dvReph dvReph_Anusvara]' lookup SingleSubstitution52;
    } ChainedContextualGSUB17;


    feature abvs {
        lookup ChainedContextualGSUB17;
    } abvs;

    feature pres {
        lookup matrai;
    } pres;

    feature rkrf {
        lookup LigatureSubstitution8;
    } rkrf;

    feature rphf {
        lookup LigatureSubstitution4;
    } rphf;

    """
    addOpenTypeFeaturesFromString(poppins_ttFont, fea)
    poppins_ttFont.save(poppins_ttFont.reader.file.name)
    i = GlyphCombinator(poppins_ttFont)
    i.get_combinations()
    assert i.glyphs['dvReph'] == 'र्'

    assert i.glyphs["dvK_RA"] == "क्र"
    assert i.glyphs['dvmI.a03-dvKA'] == 'कि'
    
    assert i.glyphs["dvmI.a03-dvK_RA"] == 'क्रि'
    assert i.glyphs['dvmI.a03-dvK_RA-dvAnusvara.amI'] ==  'क्रिं'
