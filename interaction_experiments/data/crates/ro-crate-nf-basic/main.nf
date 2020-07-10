#!/usr/bin/env nextflow

/*
 * Derived from the basic Nextflow example: https://github.com/nextflow-io/nextflow/blob/79239f05ffd1114d559aa38617759cb58a8cf8ab/tests/basic.nf
 */

params.in = "$baseDir/data/sample.fa"
params.out = "$baseDir/data/sample_rev.fa"

/*
 * Split a FASTA file into multiple files, one sequence per file
 */
process splitSequences {

    input:
    path 'input.fa' from params.in

    output:
    path 'seq_*' into records

    """
    awk '/^>/{f="seq_"++d} {print > f}' < input.fa
    """
}

/*
 * Reverse the sequences
 */
process reverse {

    input:
    path x from records

    output:
    stdout into result

    """
    cat $x | rev
    """
}

/*
 * Save channel contents to the output file
 */
result.collectFile(name: params.out)
