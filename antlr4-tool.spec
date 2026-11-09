Name:		antlr4-tool
Version:	4.13.2
Release:	4
Summary:	ANTLR 4 grammar tool
Group:		Development/Java
License:	BSD
URL:		https://www.antlr.org/
# The git tag leaves out the generated parsers and UnicodeData. This
# sources jar is the handwritten tool plus those generated sources.
# It contains no class files.
Source0:	https://repo1.maven.org/maven2/org/antlr/antlr4/%{version}/antlr4-%{version}-sources.jar
Source1:	https://raw.githubusercontent.com/antlr/antlr4/%{version}/LICENSE.txt
# Groovy's Parrot grammar shares one context class across rules.
Patch0:		antlr4-%{version}-basecontext.patch

BuildArch:	noarch
BuildRequires:	java-current-devel
BuildRequires:	antlr4 = %{version}
BuildRequires:	antlr-runtime
BuildRequires:	stringtemplate4 >= 4.3.4
BuildRequires:	treelayout
BuildRequires:	sysjar

# build-classpath belongs to javapackages-tools, which is not installed
# in this build root. These are the jars the BuildRequires above install.
# treelayout's jar is nested; the package does not ship a top-level symlink.
%global dep_cp %{_javadir}/antlr4-runtime.jar:%{_javadir}/antlr-runtime.jar:%{_javadir}/ST4.jar:%{_javadir}/treelayout/org.abego.treelayout.core.jar

%description
ANTLR 4 reads a grammar and generates a parser. This is the tool.
The runtime is the antlr4 package. UnicodeDataTemplateController is
omitted: it only regenerates UnicodeData, and that needs ICU. The
parse-tree viewer and TestRig are included. They use treelayout.
tomlj runs this tool while it builds.
The baseContext rule option lets several rules share one context
class. Getters on that class are named for the shared context, and a
repeated element stays a List getter. A grammar that does not use
the option still generates the same Java.

%prep
%setup -q -c -T -n %{name}-%{version}
jar xf %{SOURCE0}
install -m 644 %{SOURCE1} LICENSE.txt
# The controller imports com.ibm.icu. UnicodeData.java is already
# generated. The gui stays: GroovyConsole's CST inspector extends
# org.antlr.v4.gui.TestRig.
rm -f src/org/antlr/v4/unicode/UnicodeDataTemplateController.java
rm -f org/antlr/v4/unicode/UnicodeDataTemplateController.java
mkdir -p org/antlr/v4/unicode
mv src/org/antlr/v4/unicode/UnicodeData.java org/antlr/v4/unicode/UnicodeData.java
rm -rf src
find . -name '*.g' -delete
%autopatch -p1

%build
export JAVA_HOME=%{_jvmdir}/java-openjdk
export PATH=$JAVA_HOME/bin:$PATH
find org -name '*.java' > sources.list
mkdir -p classes
javac --release 11 -encoding UTF-8 \
	-cp "%{dep_cp}" \
	-d classes @sources.list
find org \( -name '*.stg' -o -name '*.st' \) > resources.list
jar cf %{name}.jar -C classes .
xargs -a resources.list jar uf %{name}.jar
cat > %{name}.pom <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.antlr</groupId>
  <artifactId>antlr4</artifactId>
  <version>%{version}</version>
  <name>ANTLR 4 Tool</name>
  <description>Grammar tool for ANTLR 4. The runtime is a separate artifact.</description>
  <url>https://www.antlr.org/</url>
  <licenses>
    <license>
      <name>BSD-3-Clause</name>
      <url>https://www.antlr.org/license.html</url>
    </license>
  </licenses>
  <dependencies>
    <dependency>
      <groupId>org.antlr</groupId>
      <artifactId>antlr4-runtime</artifactId>
      <version>%{version}</version>
    </dependency>
    <dependency>
      <groupId>org.antlr</groupId>
      <artifactId>antlr-runtime</artifactId>
      <version>3.5.3</version>
    </dependency>
    <dependency>
      <groupId>org.antlr</groupId>
      <artifactId>ST4</artifactId>
      <version>4.3.4</version>
    </dependency>
    <dependency>
      <groupId>org.abego.treelayout</groupId>
      <artifactId>org.abego.treelayout.core</artifactId>
      <version>1.0.3</version>
    </dependency>
  </dependencies>
</project>
EOF

%check
export JAVA_HOME=%{_jvmdir}/java-openjdk
export PATH=$JAVA_HOME/bin:$PATH
mkdir -p check
cat > check/Hello.g4 <<'END'
grammar Hello;
r : 'hello' ID ;
ID : [a-z]+ ;
WS : [ \t\r\n]+ -> skip ;
END
# -o keeps the grammar's directory, so run with the grammar in the
# working directory. The output is then check/out/HelloParser.java.
(
	cd check
	java -cp ../%{name}.jar:%{dep_cp} \
		org.antlr.v4.Tool -o out Hello.g4
)
test -s check/out/HelloParser.java
test -s check/out/HelloLexer.java
# Duplicate alt labels stay an error unless the rules share a context.
# Two rules can share one context class. Compile that parser and run it.
(
	cd check
	cat > Bad.g4 <<'END'
grammar Bad;
s : a | b ;
a : INT # X ;
b : INT # X ;
INT : [0-9]+ ;
END
	if java -cp ../%{name}.jar:%{dep_cp} org.antlr.v4.Tool -o bad Bad.g4 >bad.log 2>&1; then
		echo "duplicate alt label was accepted" >&2
		exit 1
	fi
	grep -q 'error(123)' bad.log
	cat > Share.g4 <<'END'
grammar Share;
file : item+ EOF ;
item : e | n ;
e : INT # Num ;
n options { baseContext = e; } : FLOAT # Num ;
INT : [0-9]+ ;
FLOAT : [0-9]+ '.' [0-9]+ ;
WS : [ \t\r\n]+ -> skip ;
END
	java -cp ../%{name}.jar:%{dep_cp} org.antlr.v4.Tool -visitor -o share Share.g4
	test -s share/ShareParser.java
	grep -q 'class NumContext extends EContext' share/ShareParser.java
	# n() is still a rule method. The getter on ItemContext is e() for both alts.
	grep -q 'final EContext n()' share/ShareParser.java
	awk '/class ItemContext /,/^	}/' share/ShareParser.java > itemctx.txt
	grep -q 'EContext e()' itemctx.txt
	if grep -q 'n()' itemctx.txt; then
		echo "shared getter kept the referenced rule name" >&2
		exit 1
	fi
	if grep -q 'visitN(' share/ShareVisitor.java; then
		echo "non-base rule leaked a visitor method" >&2
		exit 1
	fi
	grep -q 'visitE(' share/ShareVisitor.java
	mkdir -p classes
	javac --release 11 -encoding UTF-8 \
		-cp %{_javadir}/antlr4-runtime.jar \
		-d classes share/*.java
	cat > Main.java <<'END'
import org.antlr.v4.runtime.*;
public class Main {
	public static void main(String[] args) {
		ShareLexer lexer = new ShareLexer(CharStreams.fromString("1 2.5"));
		ShareParser parser = new ShareParser(new CommonTokenStream(lexer));
		parser.removeErrorListeners();
		parser.addErrorListener(new BaseErrorListener() {
			@Override public void syntaxError(Recognizer<?,?> r, Object o, int line, int c, String msg, RecognitionException e) {
				throw new RuntimeException(line + ":" + c + " " + msg);
			}
		});
		ShareParser.FileContext tree = parser.file();
		if (tree.item().size() != 2) throw new RuntimeException("items");
		for (int i = 0; i < 2; i++) {
			ShareParser.ItemContext item = tree.item(i);
			ParserRuleContext inner = item.e();
			if (inner == null) throw new RuntimeException("missing e");
			if (!(inner instanceof ShareParser.NumContext)) throw new RuntimeException("num");
			if (!(inner instanceof ShareParser.EContext)) throw new RuntimeException("ectx");
		}
		new ShareBaseVisitor<Void>().visit(tree);
		System.out.println("share_ok");
	}
}
END
	javac --release 11 -encoding UTF-8 -cp %{_javadir}/antlr4-runtime.jar:classes -d classes Main.java
	java -cp %{_javadir}/antlr4-runtime.jar:classes Main | grep -q share_ok
)
jar tf %{name}.jar | grep -q '^org/antlr/v4/gui/TestRig.class$'
jar tf %{name}.jar | grep -q '^org/antlr/v4/gui/TreeViewer.class$'

%install
sysjar install --buildroot %{buildroot} \
	--artifact %{name}.pom:%{name}.jar \
	--file-name %{name} \
	--filelist .mfiles
install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/antlr4 <<'EOF'
#!/bin/sh
exec java -cp %{_javadir}/antlr4-tool.jar:%{dep_cp} org.antlr.v4.Tool "$@"
EOF
chmod 755 %{buildroot}%{_bindir}/antlr4

%files -f .mfiles
%{_bindir}/antlr4
%doc LICENSE.txt
